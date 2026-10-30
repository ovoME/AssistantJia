"""规则、目录和推荐的可追溯 SSE 编排；有 LLM 时只据实际工具结果组织回复。"""
import asyncio
import json
import logging
import re
from collections import OrderedDict
from app.config import settings
from app.auth import active_reader
from app.agent.prompts import (KNOWLEDGE_SUMMARY_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT,
                               TOOL_SUMMARY_PROMPT)
from app.agent.tools.data_client import data_client
from app.services import local_data
from app.services.data_manager import data_manager
from data.recommendation import excludes_popular, recommendation_topic, wants_popular

SESSION_HISTORIES = OrderedDict()
logger = logging.getLogger(__name__)


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


def recommendation_limit(message, default=5):
    """提取常见的推荐数量，限制在接口允许的范围内。"""
    match = re.search(r"(\d{1,3}|[一二两三四五六七八九十]{1,3})\s*(?:本|册|部)", message or "")
    if not match:
        return default
    word = match.group(1)
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    if word.isdecimal():
        count = int(word)
    elif "十" in word:
        left, right = word.split("十", 1)
        count = digits.get(left, 1 if not left else 0) * 10 + digits.get(right, 0)
    else:
        count = digits.get(word, 0)
    return min(count, 20) if count > 0 else default


def clear_book_recommendation(message):
    """模型未选工具时，仅对明确的正向荐书请求使用本地兜底。"""
    return bool("书" in message and any(word in message for word in ("推荐", "好书", "看什么"))
                and not re.search(r"(?:不要|不用|不需要|不想|别).{0,8}推荐", message))


class LibraryAgent:
    def _format_sse(self, data):
        return "data: " + json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n\n"

    def _run_recommend(self, reader_id, question=None, session_id=None, model_args=None):
        limit = recommendation_limit(question, default=None)
        query, popular = question, None
        if model_args is not None:
            topic = model_args.get("query")
            query = topic if isinstance(topic, str) and recommendation_topic(topic) else None
            popular = not excludes_popular(question) and (
                model_args.get("popular") is True or wants_popular(question) or wants_popular(topic)
            )
            model_limit = model_args.get("limit")
            if limit is None and isinstance(model_limit, int) and not isinstance(model_limit, bool) and 1 <= model_limit <= 20:
                limit = model_limit
        limit = limit or 5
        search_terms = model_args.get("search_terms") if model_args else None
        payload = data_client.get_recommendation_bundle(
            reader_id, limit=limit, query=query, session_id=session_id, popular=popular, search_terms=search_terms)
        rows, queries = payload["recommendations"], payload["search_terms"]
        if payload.get("scope") == "catalog_recommendation_candidates":
            cards = [recommendation_card(row, payload["dataset_label"]) for row in rows]
            titles = "、".join("《" + row["title"] + "》" for row in rows[:3])
            guidance = ("请按目标院校的考试科目和教材版本核对"
                        if re.search(r"考研|备考|考试|研究生|复试", question or "")
                        else "请核对是否适合你的需求及所需版本")
            reply = (f"在已导入的书目快照中找到{titles}等相关资料。"
                     f"这些是关键词匹配的候选，{guidance}；实时可借状态和架位尚未核实。")
            if reader_id:
                reply += "书目候选没有按个人借阅历史过滤。"
            return ("recommend_books", {"limit": limit, "query": query, "search_terms": queries, "popular": popular},
                    payload, cards, reply)
        cards = [recommendation_card(row, payload["dataset_label"]) for row in rows]
        if cards:
            titles = "、".join("《" + row["title"] + "》" for row in rows[:3])
            reply = f"可借状态和架位未核实。给你挑了{titles}；推荐来自历史借阅样本。"
        elif recommendation_topic(query):
            reply = ("历史样本和本地书目没有找到直接匹配的资料，可以提供更具体的学科、书名或作者。"
                     if queries and not popular else "历史样本中没有找到与该主题直接匹配的推荐，可以换个书名、作者或类别。")
        else:
            reply = "该筛选条件下没有剩余推荐候选。"
        return "recommend_books", {"limit": limit, "query": query, "popular": popular}, payload, cards, reply

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

    def _execute(self, tool, args, reader_id, question=None, session_id=None):
        """按工具名执行只读查询；关键词命中与模型路由共用同一条路径。"""
        args = args or {}
        if tool == "recommend_books":
            return self._run_recommend(reader_id, question or args.get("query"), session_id, model_args=args)
        if tool == "get_user_borrows":
            return self._run_borrows(reader_id)
        if tool == "search_books":
            query = args.get("query") or args.get("question") or ""
            return self._run_search(search_query(query) or query)
        if tool == "search_knowledge":
            return self._run_rules(args.get("question") or args.get("query") or "")
        return None

    def _prepare(self, message, reader_id, session_id=None):
        q = message.strip()
        quoted = "《" in q
        if any(word in q for word in ["推荐", "好书", "看什么", "榜单", "热门"]):
            return self._run_recommend(reader_id, q, session_id)
        if quoted or any(word in q for word in ["找书", "查书", "搜书", "馆藏", "索书号", "架位", "书架", "几楼"]):
            return self._run_search(search_query(q))
        if not quoted and any(word in q for word in ["续借", "借期", "多久", "几天", "多少天", "几本", "几册", "多少册", "多少本", "上限", "开馆", "闭馆", "开放", "几点", "座位", "暂离", "积分", "规则", "规定", "预约", "委托", "研讨室", "假期", "充电宝", "校外", "现刊", "工具书", "报纸", "押金", "罚款"]):
            return self._run_rules(q)
        multi_answer = self._run_multimodal(q)
        if multi_answer:
            return multi_answer
        return None, {}, {}, [], "我是小嘉，可以查询本地书目、推荐图书，以及根据馆方资料回答借阅规则。实时借阅操作请在馆方系统办理。"

    def _run_multimodal(self, question):
        result = data_manager.query_multimodal_knowledge(question)
        if result:
            return "query_multimodal_data", {"domain": result["domain"], "query": question}, result, [], result["reply"]
        return None

    async def _route_with_llm(self, message, reader_id, history=None):
        """模型先判断只读意图；None 表示不可用，(None,{}) 表示无需工具。"""
        if not self._llm_ready():
            return None
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            from app.agent.tools import READ_TOOLS
            llm = ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY,
                             base_url=settings.LLM_BASE_URL, temperature=0,
                             timeout=15, max_retries=0)
            messages = [SystemMessage(content=ROUTER_PROMPT)]
            for item in (history or [])[-10:]:
                if item.get("role") == "user":
                    messages.append(HumanMessage(content=item["content"]))
                elif item.get("role") == "assistant":
                    messages.append(AIMessage(content=item["content"]))
            if not history or history[-1].get("role") != "user" or history[-1].get("content") != message:
                messages.append(HumanMessage(content=message))
            result = await llm.bind_tools(READ_TOOLS).ainvoke(messages)
            calls = getattr(result, "tool_calls", None) or []
            if not calls:
                return (None, {})
            call = calls[0]
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            allowed = {"search_books", "recommend_books", "search_knowledge", "get_user_borrows"}
            if name not in allowed or not isinstance(args, dict):
                return None
            if name in {"search_books", "search_knowledge"}:
                value = args.get("query") or args.get("question")
                if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                    return None
            if name == "recommend_books":
                value, popular = args.get("query"), args.get("popular")
                if value is not None and (not isinstance(value, str) or len(value) > 2000):
                    return None
                if popular is not None and not isinstance(popular, bool):
                    return None
            return name, args
        except Exception as exc:
            logger.warning("Model intent routing failed: type=%s status=%s", type(exc).__name__,
                           getattr(exc, "status_code", None))
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
        """按实际工具证据组织回复；模型缺失或调用失败时使用本地回答。"""
        # 结构化多源摘要是按导入样本计算的，直接回传可避免模型添加未核验的统计结论。
        if tool == "query_multimodal_data":
            return fallback
        # 书目候选只证明关键词匹配，由代码说明来源与大纲限制，避免模型补造考试要求。
        if payload.get("scope") == "catalog_recommendation_candidates":
            return fallback
        if not self._llm_ready():
            return fallback
        # 借阅为空（未登录，或确实没借）：直接给确定提示，否则模型会向读者索要借书证号，
        # 而身份其实来自登录态，报证件号没有用。
        if tool == "get_user_borrows" and not payload.get("borrows"):
            return fallback
        # 空结果不能由模型补造书目。
        if tool == "recommend_books" and not payload.get("recommendations"):
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
            # 泛泛的模型回复会掩盖换批结果；没有提到本批书名时用实际书目生成回复。
            if tool == "recommend_books" and not any(row["title"] in text for row in payload["recommendations"]):
                return fallback
            if tool == "search_knowledge":
                return text.strip() + self._knowledge_suffix(payload)
            if tool == "get_user_borrows":
                return text.strip() + "\n\n借阅状态以馆方系统为准，续借和逾期处理需走馆方渠道。"
            return text.strip() + "\n\n依据本次历史数据或静态书目；实时可借状态、架位和业务办理尚未核实。"
        except Exception as exc:
            logger.warning("Model reply composition failed: type=%s status=%s", type(exc).__name__,
                           getattr(exc, "status_code", None))
            return fallback

    async def stream_chat(self, message, session_id="default", reader_id=None):
        history = get_session_history(session_id)
        history.append({"role": "user", "content": message})
        history[:] = history[-40:]
        context_token = active_reader.set(reader_id)
        try:
            degraded = False
            tool, args, payload, cards = None, {}, {}, []
            reply = "我是小嘉，可以查询本地书目、推荐图书，以及根据馆方资料回答借阅规则。实时借阅操作请在馆方系统办理。"
            yield self._format_sse({"type": "thought", "content": "正在理解你的问题…"})
            routed = await self._route_with_llm(message, reader_id, history)
            used_local_fallback = self._llm_ready() and routed is None
            try:
                yield self._format_sse({"type": "thought", "content": "正在查询相关数据…"})
                if routed is None:
                    # 模型未配置或调用失败时才使用关键词兜底。
                    prepared = await asyncio.to_thread(self._prepare, message, reader_id, session_id)
                elif routed[0] is None:
                    # 未调用工具时，明确荐书请求仍需真实书目，不能由模型自行编造。
                    if clear_book_recommendation(message):
                        prepared = await asyncio.to_thread(self._prepare, message, reader_id, session_id)
                        used_local_fallback = True
                    else:
                        prepared = await asyncio.to_thread(self._run_multimodal, message)
                else:
                    prepared = await asyncio.to_thread(self._execute, routed[0], routed[1], reader_id, message, session_id)
                if prepared:
                    tool, args, payload, cards, reply = prepared
            except (OSError, ValueError, PermissionError, RuntimeError):
                reply = "相关数据服务当前未就绪，请稍后重试；需要实时业务请使用馆方系统或咨询总服务台。"
                degraded = True
            if tool:
                yield self._format_sse({"type": "tool_call", "tool": tool, "args": args})
            for card in cards:
                yield self._format_sse({"type": "card", "card_type": "book", "data": card})
            # 所有分支（闲聊、书目、推荐、规则）都经大模型组织语言；
            # 数据服务异常时保留原始提示，不交给模型改写。
            if not degraded:
                reply = await self._compose_reply(message, tool, args, payload, reply, history)
            if used_local_fallback:
                reply += "\n\n模型未能完成意图识别，本次按本地规则处理。"
            for start in range(0, len(reply), 24):
                yield self._format_sse({"type": "content", "token": reply[start:start + 24]})
                await asyncio.sleep(0)
            history.append({"role": "assistant", "content": reply})
            history[:] = history[-40:]
            yield self._format_sse({"type": "done"})
        finally:
            active_reader.reset(context_token)


agent = LibraryAgent()
