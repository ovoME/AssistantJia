from typing import List
from fastapi import APIRouter, Depends, Query, UploadFile, File
from app.auth import require_admin
from app.schemas.common import ApiResponse
from app.schemas.admin import AdminSummary, CategoryStat, BookStat, PublisherStat, PurchaseAdviceRequest, BookReviewRequest
from app.services.local_data import borrowing, usage
from pathlib import Path
import json
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"], dependencies=[Depends(require_admin)])


from app.config import PROJECT_ROOT

# 用户上传物独立存放；data/raw 是主办方原始数据目录，保持只读
DATA_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"


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


@router.get("/data/files", response_model=ApiResponse[List[dict]])
def list_data_files():
    """列出已上传到 data/uploads 的数据文件"""
    DATA_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in DATA_UPLOAD_DIR.iterdir():
        if p.is_file() and p.suffix in (".xlsx", ".xls", ".csv"):
            stat = p.stat()
            files.append({
                "id": p.stem,
                "filename": p.name,
                "kind": "borrow" if "借阅" in p.name else "other",
                "rows": None,
                "size_kb": round(stat.st_size / 1024, 1),
                "status": "ready",
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    files.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return ApiResponse.ok(data=files)


@router.post("/data/upload", response_model=ApiResponse[dict])
async def upload_data_file(file: UploadFile = File(...)):
    """上传数据文件到 data/uploads/"""
    from fastapi import HTTPException
    ALLOWED_SUFFIX = {".xlsx", ".xls", ".csv"}
    MAX_BYTES = 50 * 1024 * 1024
    # 复用模块级目录，避免上传与列表指向不同位置
    DATA_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 只取 basename，任何目录成分都丢掉
    name = Path(file.filename or "").name
    if not name or name in {".", ".."} or Path(name).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(400, "仅支持 .xlsx / .xls / .csv 文件")

    dest = DATA_UPLOAD_DIR / name

    # 2) 分块读，超限立即中止并清理
    total = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "文件不能超过 50MB")
            out.write(chunk)

    # 3) 兜底：确认最终路径确实落在目标目录内
    if not dest.resolve().is_relative_to(DATA_UPLOAD_DIR.resolve()):
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "非法文件名")

    return ApiResponse.ok(data={
        "id": dest.stem,
        "filename": dest.name,
        "kind": "borrow" if "借阅" in dest.name else "other",
        "rows": None,
        "size_kb": round(total / 1024, 1),
        "status": "processing",
        "uploaded_at": datetime.now().isoformat(),
        "message": "文件已上传，需运行数据处理脚本后生效",
    })


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
