from fastapi import APIRouter
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=ApiResponse)
async def health_check():
    """系统健康检查接口"""
    return ApiResponse.ok(data={"status": "healthy", "service": "AssistantJia Backend"})
