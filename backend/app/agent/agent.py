"""规则、目录和推荐的可追溯 SSE 编排；有 LLM 时只据实际工具结果组织回复。"""
import asyncio
import json
import re
from collections import OrderedDict
from app.config import settings
from app.auth import active_reader
from app.agent.prompts import (KNOWLEDGE_SUMMARY_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT,
                               TOOL_SUMMARY_PROMPT)
from app.agent.tools.data_client import data_client
from app.services import local_data
from app.services.data_manager import data_manager

SESSION_HISTORIES = OrderedDict()


def get_session_history(session_id):
    if session_id not in SESSION_HISTORIES:
        if len(SESSION_HISTORIES) >= 500:
            SESSION_HISTORIES.popitem(last=False)
        SESSION_HISTORIES[session_id] = []
    return SESSION_HISTORIES[session_id]


def recommendation_card(row, label):
    return {**row, "location": None, "available": None, "status": "unknown", "is_live": False,
            "dataset_label": label, "reservation_supported": False}


def search_query(message):
    quoted = re.search(r"《([^》]+)》", message)
    if quoted:
        return quoted.group(1)
    text = re.sub(r"^(请|麻烦|帮我|我想|给我|一下|查找|查询|查一下|查|找|搜|搜索|有关|关于)+", "", message.strip())
    return re.sub(r"(相关的书|相关图书|的书|在哪.*|在几楼.*|有没有.*|可以借吗.*|能借吗.*|[？?。])$", "", text).strip()


class LibraryAgent:
    def _format_sse(self, data):
        return "data: " + json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n\n"

    def _run_recommend(self, reader_id):
        service = local_data.borrowing()
        rows = data_client.get_recommendations(reader_id)
        cards = [recommendation_card(row, service.engine.dataset_label) for row in rows]
        reply = ("这是根据历史借阅样本生成的" + ("个性化" if reader_id else "热门")
                 + "推荐；可借状态和架位尚未核实。") if cards else "该筛选条件下没有剩余推荐候选。"
        return "recommend_books", {"limit": 5}, {"recommendations": rows, **service.metadata()}, cards, reply

    def _run_search(self, query):
        payload = local_data.search_books_response(query, 5)
        cards = [{**row, "dataset_label": payload["dataset_label"],
                  "reservation_supported": row.get("reservation_supported", False)}
                 for row in payload["data"]]
        reply = ("在本地书目快照中找到以下图书，索书号见卡片；未核实实时可借数量和架位。"
                 if cards else "本地书目没有匹配结果，可以换用书名、作者或索书号关键词。")
        if cards and settings.DATA_PROFILE == "integration":
            reply = "找到以下模拟联调图书。卡片架位、可借数量和状态均为模拟数据，非馆方实时结果。"
        return "search_books", {"query": query}, payload, cards, reply

    def _run_rules(self, question):
        info = data_client.search_rules_knowledge(question)
        reply = info["answer"]
        if info["sources"]:
            reply += "\n\n来源：\n" + "\n".join(f"[{i}] {row['title']}：{row['url']}"
                                                for i, row in enumerate(info["sources"], 1))
            reply += "\n核对日期：" + info["retrieved_at"][:10] + "。临时安排以馆方公告为准。"
        return "search_knowledge", {"question": question}, info, [], reply

    def _run_borrows(self, reader_id):
        if not reader_id:
            return ("get_user_borrows", {}, {"status": "unauthenticated"}, [],
                    "查自己的借阅记录得先登录一下，我这边看不到你的身份。登录后我再帮你看借了哪些、什么时候到期。")
        records = data_client.get_user_borrows(reader_id)
        count = len(records) if isinstance(records, list) else 0
        reply = (f"你当前在借 {count} 本，到期时间在上面的记录里。" if count else "你现在没有在借的书。")
        return "get_user_borrows", {"reader_id": reader_id}, {"borrows": records}, [], reply

    def _execute(self, tool, args, reader_id):
        """按工具名执行只读查询；关键词命中与模型路由共用同一条路径。"""
        args = args or {}
        if tool == "recommend_books":
            return self._run_recommend(reader_id)
        if tool == "get_user_borrows":
            return self._run_borrows(reader_id)
        if tool == "search_books":
            query = args.get("query") or args.get("question") or ""
            return self._run_search(search_query(query) or query)
        if tool == "search_knowledge":
            return self._run_rules(args.get("question") or args.get("query") or "")
        return None

    def _prepare(self, message, reader_id):
        q = message.strip()
        quoted = "《" in q
        if any(word in q for word in ["推荐", "好书", "看什么", "榜单", "热门"]):
            return self._run_recommend(reader_id)
        if quoted or any(word in q for word in ["找书", "查书", "搜书", "馆藏", "索书号", "架位", "书架", "几楼"]):
            return self._run_search(search_query(q))
        if not quoted and any(word in q for word in ["续借", "借期", "多久", "几天", "多少天", "几本", "几册", "多少册", "多少本", "上限", "开馆", "闭馆", "开放", "几点", "座位", "暂离", "积分", "规则", "规定", "预约", "委托", "研讨室", "假期", "充电宝", "校外", "现刊", "工具书", "报纸", "押金", "罚款"]):
            return self._run_rules(q)
        multi_answer = data_manager.query_multimodal_knowledge(q)
        if multi_answer:
            return (
                "query_multimodal_data",
                {"domain": multi_answer["domain"], "query": q},
                multi_answer,
                [],
                multi_answer["reply"],
            )
        return None, {}, {}, [], "我是小嘉，可以查询本地书目、推荐图书，以及根据馆方资料回答借阅规则。实时借阅操作请在馆方系统办理。"

    async def _route_with_llm(self, message, reader_id):
        """关键词没命中时让模型判断该查哪一项；模型不可用或拿不准时返回 None 走对话。"""
        if not self._llm_ready():
            return None
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            from app.agent.tools import READ_TOOLS
            llm = ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY,
                             base_url=settings.LLM_BASE_URL, temperature=0,
                             timeout=15, max_retries=0)
            result = await llm.bind_tools(READ_TOOLS).ainvoke(
                [SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=message)])
            calls = getattr(result, "tool_calls", None) or []
            if not calls:
                return None
            call = calls[0]
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            return (name, args or {}) if name else None
        except Exception:
            return None

    def _llm_ready(self):
        key = settings.LLM_API_KEY
        return bool(key) and not key.startswith("sk-your")

    def _knowledge_suffix(self, payload):
        """来源与核对日期由代码固定追加，不交给模型生成，避免引用被改写或漏掉。"""
        if not payload.get("sources"):
            return ""
        lines = "\n".join(f"[{i}] {row['title']}：{row['url']}"
                          for i, row in enumerate(payload["sources"], 1))
        return ("\n\n来源：\n" + lines + "\n核对日期：" + payload["retrieved_at"][:10]
                + "。临时安排以馆方公告为准。")

    async def _compose_reply(self, message, tool, args, payload, fallback, history):
        """每一条用户消息都交给大模型组织语言；模型缺失或调用失败时退回规则原文。"""
        # 结构化多源摘要是按导入样本计算的，直接回传可避免模型添加未核验的统计结论。
        if tool == "query_multimodal_data":
            return fallback
        if not self._llm_ready():
            return fallback
        # 借阅为空（未登录，或确实没借）：直接给确定提示，否则模型会向读者索要借书证号，
        # 而身份其实来自登录态，报证件号没有用。
        if tool == "get_user_borrows" and not payload.get("borrows"):
            return fallback
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
        except ImportError:
            return fallback
        try:
            if tool is None:
                llm = ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY,
                                 base_url=settings.LLM_BASE_URL, temperature=0.7,
                                 timeout=20, max_retries=0)
                msgs = [SystemMessage(content=SYSTEM_PROMPT)]
                for h in history[-10:]:
                    if h["role"] == "user":
                        msgs.append(HumanMessage(content=h["content"]))
                    elif h["role"] == "assistant":
                        msgs.append(AIMessage(content=h["content"]))
                result = await llm.ainvoke(msgs)
                text = result.content if isinstance(result.content, str) else ""
                return text.strip() or fallback
            instruction = SYSTEM_PROMPT + (KNOWLEDGE_SUMMARY_PROMPT if tool == "search_knowledge"
                                           else TOOL_SUMMARY_PROMPT)
            llm = ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY,
                             base_url=settings.LLM_BASE_URL, temperature=0, timeout=20, max_retries=0)
            result = await llm.ainvoke([
                SystemMessage(content=instruction),
                HumanMessage(content=message),
                AIMessage(content="", tool_calls=[{"name": tool, "args": args,
                                                   "id": "evidence", "type": "tool_call"}]),
                ToolMessage(content=json.dumps(payload, ensure_ascii=False), tool_call_id="evidence"),
            ])
            text = result.content if isinstance(result.content, str) else ""
            if not text.strip():
                return fallback
            if tool == "search_knowledge":
                return text.strip() + self._knowledge_suffix(payload)
            if tool == "get_user_borrows":
                return text.strip() + "\n\n借阅状态以馆方系统为准，续借和逾期处理需走馆方渠道。"
            return text.strip() + "\n\n依据本次历史数据或静态书目；实时可借状态、架位和业务办理尚未核实。"
        except Exception:
            return fallback

    async def stream_chat(self, message, session_id="default", reader_id=None):
        history = get_session_history(session_id)
        history.append({"role": "user", "content": message})
        history[:] = history[-40:]
        context_token = active_reader.set(reader_id)
        try:
            degraded = False
            try:
                tool, args, payload, cards, reply = await asyncio.to_thread(self._prepare, message, reader_id)
            except (OSError, ValueError, PermissionError, RuntimeError):
                tool, args, payload, cards = None, {}, {}, []
                reply = "相关数据服务当前未就绪，请稍后重试；需要实时业务请使用馆方系统或咨询总服务台。"
                degraded = True
            # 关键词没命中时，让模型判断是不是该查数据（例如"三体在不在馆"这种说法）。
            if tool is None and not degraded:
                routed = await self._route_with_llm(message, reader_id)
                if routed:
                    try:
                        executed = await asyncio.to_thread(self._execute, routed[0], routed[1], reader_id)
                    except (OSError, ValueError, PermissionError, RuntimeError):
                        executed = None
                    if executed:
                        tool, args, payload, cards, reply = executed
            if tool:
                yield self._format_sse({"type": "thought", "content": "正在查询已加载的数据与已核对规则…"})
                yield self._format_sse({"type": "tool_call", "tool": tool, "args": args})
            for card in cards:
                yield self._format_sse({"type": "card", "card_type": "book", "data": card})
            # 所有分支（闲聊、书目、推荐、规则）都经大模型组织语言；
            # 数据服务异常时保留原始提示，不交给模型改写。
            if not degraded:
                reply = await self._compose_reply(message, tool, args, payload, reply, history)
            for start in range(0, len(reply), 24):
                yield self._format_sse({"type": "content", "token": reply[start:start + 24]})
                await asyncio.sleep(0)
            history.append({"role": "assistant", "content": reply})
            history[:] = history[-40:]
            yield self._format_sse({"type": "done"})
        finally:
            active_reader.reset(context_token)


agent = LibraryAgent()
