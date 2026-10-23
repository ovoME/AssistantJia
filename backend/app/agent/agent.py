"""
智能体 Agent 核心编排器
支持大模型工具调用 (Tool Calling) 与 SSE 流式事件派发，并具备离线/无Key智能容灾机制。
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from datetime import datetime

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools.data_client import data_client
from app.schemas.book import Book

# 内存会话历史存储 (支持多轮对话)
SESSION_HISTORIES: Dict[str, List[Dict[str, str]]] = {}

def get_session_history(session_id: str) -> List[Dict[str, str]]:
    if session_id not in SESSION_HISTORIES:
        SESSION_HISTORIES[session_id] = []
    return SESSION_HISTORIES[session_id]

class LibraryAgent:
    """小嘉智能体大脑"""

    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT

    def _format_sse(self, data: Dict[str, Any]) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_chat(
        self,
        message: str,
        session_id: str = "default",
        reader_id: str = "2023001"
    ) -> AsyncGenerator[str, None]:
        """
        核心流式对话生成器：
        返回格式兼容前端 types/index.ts 规定的 SSE 事件结构
        """
        history = get_session_history(session_id)
        history.append({"role": "user", "content": message})

        # 检查是否配置了有效的线上大模型 API Key
        has_api_key = bool(settings.LLM_API_KEY and not settings.LLM_API_KEY.startswith("sk-your"))

        if has_api_key:
            # 走线上 OpenAI / DeepSeek 真实模型调用
            try:
                from langchain_openai import ChatOpenAI
                from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
                from app.agent.tools import ALL_TOOLS

                llm = ChatOpenAI(
                    model=settings.LLM_MODEL,
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                    temperature=settings.LLM_TEMPERATURE,
                    streaming=True
                )
                llm_with_tools = llm.bind_tools(ALL_TOOLS)

                messages = [SystemMessage(content=self.system_prompt)]
                for h in history[-6:]: # 保留最近6轮
                    if h["role"] == "user":
                        messages.append(HumanMessage(content=h["content"]))
                    else:
                        messages.append(AIMessage(content=h["content"]))

                # 阶段 1：首轮调用判断是否需要工具
                yield self._format_sse({"type": "thought", "content": "小嘉正在理解你的问题，分析是否需要查询图书馆系统..."})
                await asyncio.sleep(0.05)

                ai_msg = await llm_with_tools.ainvoke(messages)
                tool_calls = getattr(ai_msg, "tool_calls", [])

                if tool_calls:
                    # 触发了工具调用
                    for tc in tool_calls:
                        tool_name = tc.get("name")
                        tool_args = tc.get("args", {})
                        yield self._format_sse({
                            "type": "thought",
                            "content": f"正在调用【{tool_name}】查询最新馆藏与业务数据..."
                        })
                        yield self._format_sse({
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_args
                        })
                        await asyncio.sleep(0.05)

                        # 执行工具并根据结果发送卡片
                        if tool_name == "search_books":
                            q = tool_args.get("query", message)
                            books = data_client.search_books_opac(query=q)
                            for b in books:
                                yield self._format_sse({
                                    "type": "card",
                                    "card_type": "book",
                                    "data": b
                                })
                        elif tool_name == "recommend_books":
                            recs = data_client.get_recommendations(reader_id=reader_id)
                            for r in recs:
                                # 转换为图书卡片展示
                                yield self._format_sse({
                                    "type": "card",
                                    "card_type": "book",
                                    "data": {
                                        "title": r["title"],
                                        "author": r["author"],
                                        "isbn": r["isbn"],
                                        "call_number": r["call_number"],
                                        "location": f"推荐理由: {r['reason']}",
                                        "available": 1,
                                        "status": "推荐"
                                    }
                                })

                    # 第二阶段：让大模型根据工具结果流式组织自然语言回复
                    # 简化多步流式输出
                    final_stream = llm.astream([
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=f"用户提问：{message}\n工具查询已完成并生成了对应卡片。请用亲切靠谱的嘉庚学长口吻，对结果做简明总结和温馨提醒。")
                    ])
                    full_reply = ""
                    async for chunk in final_stream:
                        token = chunk.content
                        if token:
                            full_reply += token
                            yield self._format_sse({"type": "content", "token": token})
                    history.append({"role": "assistant", "content": full_reply})
                    yield self._format_sse({"type": "done"})
                    return

                else:
                    # 无需工具调用，直接流式回答（如闲聊、问候或超纲示弱）
                    full_reply = ""
                    direct_stream = llm.astream(messages)
                    async for chunk in direct_stream:
                        token = chunk.content
                        if token:
                            full_reply += token
                            yield self._format_sse({"type": "content", "token": token})
                    history.append({"role": "assistant", "content": full_reply})
                    yield self._format_sse({"type": "done"})
                    return

            except Exception as e:
                yield self._format_sse({
                    "type": "thought",
                    "content": f"大模型接口响应异常({str(e)})，正在切换到嘉庚本地业务规则引擎..."
                })
                # 出现网络或 Key 异常时，优雅降级走下方规则引擎

        # ==========================================
        # 降级/本地高可用业务引擎 (无需联网或 Key 亦可自测)
        # ==========================================
        q = message.strip().lower()

        # 意图 1：查馆藏/架位
        if any(kw in q for kw in ["三体", "找书", "查书", "架位", "书架", "索书号", "借本", "馆藏", "有吗", "在几楼"]):
            yield self._format_sse({"type": "thought", "content": "正在检索嘉庚学院图书馆 OPAC 馆藏数据库与架位系统..."})
            await asyncio.sleep(0.15)
            yield self._format_sse({"type": "tool_call", "tool": "search_books", "args": {"query": message}})
            await asyncio.sleep(0.15)

            books = data_client.search_books_opac(query=message)
            for b in books:
                yield self._format_sse({"type": "card", "card_type": "book", "data": b})

            reply_text = f"学弟学妹好！已在馆藏系统为你检索到相关图书。\n每本书卡片上已注明【索书号】和【具体架位】。如果图书在馆，可以直接去架位取书；点击卡片上的“预约”按钮也可以在线锁定借阅哦～"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        # 意图 2：续借咨询或操作
        elif any(kw in q for kw in ["续借", "延长", "快到期", "到期"]):
            yield self._format_sse({"type": "thought", "content": "正在查询你的在借图书与续借权限..."})
            await asyncio.sleep(0.15)
            borrows = data_client.get_user_borrows(reader_id)
            reply_text = "关于续借，小嘉提醒你：\n1. 普通图书借期 30 天，可自助续借 1 次（延长 30 天）；\n2. 你可以在界面快捷菜单点击「我的借阅」，每本可续图书右侧均有【一键续借】按钮；\n3. 已被其他读者预约、或已超期的图书不能办理续借哦！"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        # 意图 3：规章与制度（RAG 知识库）
        elif any(kw in q for kw in ["借几天", "借期", "借几本", "上限", "开放时间", "开馆", "闭馆", "几点", "研讨室", "自习室", "座位"]):
            yield self._format_sse({"type": "thought", "content": "正在检索嘉庚学院读者规章制度知识库..."})
            await asyncio.sleep(0.15)
            rule_info = data_client.search_rules_knowledge(question=message)
            reply_text = f"学弟学妹，查到了相关规程（参考《{rule_info['source']}》）：\n\n{rule_info['answer']}"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        # 意图 4：图书推荐
        elif any(kw in q for kw in ["推荐", "好书", "看什么", "榜单", "热门"]):
            yield self._format_sse({"type": "thought", "content": "正在基于全校历史借阅数据与你的偏好计算推荐书单..."})
            await asyncio.sleep(0.15)
            recs = data_client.get_recommendations(reader_id)
            for r in recs:
                yield self._format_sse({
                    "type": "card",
                    "card_type": "book",
                    "data": {
                        "title": r["title"],
                        "author": r["author"],
                        "isbn": r["isbn"],
                        "call_number": r["call_number"],
                        "location": f"推荐理由: {r['reason']}",
                        "available": 1,
                        "status": "推荐"
                    }
                })
            reply_text = "为你精心挑选了以上热门与契合你借阅方向的图书，点击卡片即可查看或预约借阅！"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        # 意图 5：超纲/无关问题 -> 示弱与转人工兜底
        elif any(kw in q for kw in ["天气", "高数", "股票", "游戏", "代码", "微积分"]):
            reply_text = "哈哈，这道题超纲啦！学长是嘉庚学院图书馆的专属数字馆员，平时最擅长的是帮你查书、找架位、办借阅和解答图书馆规定。\n如果你在图书馆遇到难解的问题，也可以前往主楼总服务台咨询老师，或致电 0596-6288455 哦！"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        # 默认通用回复
        else:
            reply_text = "学弟学妹好呀！我是图书馆AI馆员「小嘉」。你可以问我：\n• “帮我查一下《三体》在几楼哪个架位”\n• “图书一般可以借多少天，怎么续借”\n• “根据我的借阅推荐几本好书”\n有什么我可以帮你的吗？"
            for char in reply_text:
                yield self._format_sse({"type": "content", "token": char})
                await asyncio.sleep(0.015)

        history.append({"role": "assistant", "content": reply_text})
        yield self._format_sse({"type": "done"})

agent = LibraryAgent()
