from typing import List
from fastapi import APIRouter, Depends, Query
from app.auth import require_admin
from app.schemas.common import ApiResponse
from app.schemas.admin import AdminSummary, CategoryStat, BookStat, PublisherStat, PurchaseAdviceRequest, BookReviewRequest
from app.services.local_data import borrowing, usage

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"], dependencies=[Depends(require_admin)])


from app.config import PROJECT_ROOT

@router.get("/stats/summary", response_model=ApiResponse[AdminSummary])
def get_summary_stats():
    service = borrowing()
    return ApiResponse.ok(data=AdminSummary(**service.summary, **service.metadata()), **service.metadata())


@router.get("/stats/hot-books", response_model=ApiResponse[List[BookStat]])
def get_hot_books_stats(limit: int = Query(10, ge=1, le=100)):
    service = borrowing()
    return ApiResponse.ok(data=service.engine.hot_books(limit=limit), **service.metadata())


@router.get("/stats/categories", response_model=ApiResponse[List[CategoryStat]])
def get_category_stats():
    service = borrowing()
    return ApiResponse.ok(data=service.categories, **service.metadata())


@router.get("/stats/publishers", response_model=ApiResponse[List[PublisherStat]])
def get_publisher_stats(limit: int = Query(10, ge=1, le=100)):
    service = borrowing()
    return ApiResponse.ok(data=service.publishers[:limit], **service.metadata())


@router.get("/stats/trend", response_model=ApiResponse[list])
def get_trend(days: int = Query(30, ge=1, le=366)):
    service = borrowing()
    rows = service.trend(days)
    return ApiResponse.ok(data=rows, message="按样本日期汇总，窗口终点为样本末日。" if rows else "借阅源没有日期，无法生成每日趋势。", **service.metadata())


@router.get("/stats/usage", response_model=ApiResponse[dict])
def get_usage():
    report = usage()
    return ApiResponse.ok(data=report, dataset_label=report["dataset_label"], is_live=False,
                          scope="separate_source_aggregates")


@router.post("/purchase-advice", response_model=ApiResponse[dict])
def generate_purchase_advice(req: PurchaseAdviceRequest = PurchaseAdviceRequest()):
    service = borrowing()
    return ApiResponse.ok(data=service.purchase_advice(req.focus_category), **service.metadata())


@router.post("/book-review", response_model=ApiResponse)
def generate_book_review(req: BookReviewRequest):
    return ApiResponse.fail(code=4002, message="尚无可核实的书评来源，请查看馆方推荐或图书介绍。")


@router.get("/config/llm", response_model=ApiResponse[dict])
def get_llm_config():
    """获取当前 LLM 配置（API key 脱敏）"""
    from app.config import settings
    key = settings.LLM_API_KEY or ""
    masked = f"{key[:4]}****{key[-4:]}" if len(key) >= 16 else ("****" if key else "未配置")
    return ApiResponse.ok(data={
        "api_key": masked,
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
        "temperature": settings.LLM_TEMPERATURE,
        "is_configured": bool(key),
    })


@router.put("/config/llm", response_model=ApiResponse[dict])
def update_llm_config(payload: dict):
    """更新 LLM 配置（写入 .env）"""
    from app.config import settings
    # 更新运行时配置
    if "api_key" in payload and payload["api_key"] and "****" not in payload["api_key"]:
        settings.LLM_API_KEY = payload["api_key"]
    if "base_url" in payload:
        settings.LLM_BASE_URL = payload["base_url"]
    if "model" in payload:
        settings.LLM_MODEL = payload["model"]
    if "temperature" in payload:
        settings.LLM_TEMPERATURE = float(payload["temperature"])
    # 写回 .env
    env_path = PROJECT_ROOT / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    # 更新或追加 LLM 配置行
    def upsert(lines, key, value):
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        return lines
    lines = upsert(lines, "LLM_API_KEY", settings.LLM_API_KEY or "")
    lines = upsert(lines, "LLM_BASE_URL", settings.LLM_BASE_URL)
    lines = upsert(lines, "LLM_MODEL", settings.LLM_MODEL)
    lines = upsert(lines, "LLM_TEMPERATURE", str(settings.LLM_TEMPERATURE))
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ApiResponse.ok(data={
        "message": "配置已保存，重启后端后生效",
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
    })
