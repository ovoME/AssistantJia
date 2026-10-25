import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.auth import reader_identity, resolve_reader
from app.config import settings
from app.schemas.chat import ChatRequest
from app.schemas.common import ApiResponse
from app.agent.agent import agent, get_session_history

router = APIRouter(tags=["Chat"])


def owner(request, identity):
    cookie = request.cookies.get("xiaojia_session", "")
    if not cookie or len(cookie) != 32 or any(c not in "0123456789abcdef" for c in cookie):
        cookie = uuid.uuid4().hex
    return ("reader:" + identity if identity else "visitor:" + cookie), cookie


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request, identity=Depends(reader_identity)):
    reader = resolve_reader(req.reader_id, identity)
    principal, cookie = owner(request, identity)
    generator = agent.stream_chat(req.message, principal + "/" + req.session_id, reader)
    response = StreamingResponse(generator, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    response.set_cookie("xiaojia_session", cookie, httponly=True, secure=settings.COOKIE_SECURE,
                        samesite="lax", max_age=86400)
    return response


@router.get("/chat/history/{session_id}", response_model=ApiResponse)
def get_history_endpoint(session_id: str, request: Request, identity=Depends(reader_identity)):
    principal, _ = owner(request, identity)
    return ApiResponse.ok(data=get_session_history(principal + "/" + session_id))
