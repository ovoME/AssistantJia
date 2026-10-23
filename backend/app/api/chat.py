from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.schemas.common import ApiResponse
from app.agent.agent import agent, get_session_history

router = APIRouter(tags=["Chat"])

@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    智能体对话接口 (SSE 流式输出)
    返回 text/event-stream 格式数据流
    """
    generator = agent.stream_chat(
        message=req.message,
        session_id=req.session_id,
        reader_id=req.reader_id or "2023001"
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/chat/history/{session_id}", response_model=ApiResponse)
async def get_history_endpoint(session_id: str):
    """获取指定会话的历史记录"""
    history = get_session_history(session_id)
    return ApiResponse.ok(data=history)
