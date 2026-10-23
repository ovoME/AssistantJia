"""
FastAPI 主应用入口
「小嘉」图书馆AI智能体 (AssistantJia) 后端服务
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router
from app.api.health import router as health_router
from app.api.chat import router as chat_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="厦门大学嘉庚学院第二届AI应用创新大赛 - 「小嘉」图书馆AI智能体后端 API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 允许跨域请求 (适配 Vue 3 本地开发与生产部署)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
# 1. 挂载 /api 前缀路由 (对应前端实际请求)
app.include_router(api_router, prefix=settings.API_PREFIX)

# 2. 根路径挂载常用路由以满足规范契约与快速探针
app.include_router(health_router)
app.include_router(chat_router)

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "欢迎使用「小嘉」图书馆AI智能体后端系统",
        "docs": "/docs",
        "health": "/health",
        "api_prefix": settings.API_PREFIX
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
