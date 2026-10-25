from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
from app.schemas.book import Book

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="读者提问内容")
    session_id: str = Field(default="default_session", max_length=100, description="会话ID")
    reader_id: Optional[str] = Field(default=None, max_length=100, description="须与认证身份一致")

class ChatHistoryMessage(BaseModel):
    role: str = Field(..., description="user 或 assistant")
    content: str
    timestamp: Optional[str] = None

# 后端 SSE 事件数据类型
class SseThoughtEvent(BaseModel):
    type: Literal["thought"] = "thought"
    content: str

class SseToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    args: Dict[str, Any]

class SseContentEvent(BaseModel):
    type: Literal["content"] = "content"
    token: str

class SseCardEvent(BaseModel):
    type: Literal["card"] = "card"
    card_type: Literal["book"] = "book"
    data: Book

class SseDoneEvent(BaseModel):
    type: Literal["done"] = "done"

class SseErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str

SseEvent = Union[
    SseThoughtEvent,
    SseToolCallEvent,
    SseContentEvent,
    SseCardEvent,
    SseDoneEvent,
    SseErrorEvent
]
