import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth import require_admin
from app.schemas.admin import DataFileInfo
from app.schemas.common import ApiResponse
from app.services.data_manager import DATA_CATEGORIES, IMPORTED_DIR, data_manager

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
ALLOWED_SUFFIXES = {".xlsx", ".csv"}

router = APIRouter(
    prefix="/admin/data",
    tags=["Admin Data Management"],
    dependencies=[Depends(require_admin)],
)

CATEGORY_KIND_MAP = {
    "borrow": "borrow",
    "reader": "catalog",
    "gate_flow": "gate",
    "gate_swipe": "gate",
    "seats": "seat",
    "seminar": "room",
    "exam": "other",
    "scholars": "other",
}


def guess_category(filename: str) -> tuple[str, str]:
    """根据文件名推断所属业务类别及前端 kind。"""
    fn = filename.lower()
    if any(k in fn for k in ["借阅", "图书", "book", "borrow"]):
        return "borrow", "borrow"
    if any(k in fn for k in ["读者", "reader", "user"]):
        return "reader", "catalog"
    if any(k in fn for k in ["刷卡", "swipe"]):
        return "gate_swipe", "gate"
    if any(k in fn for k in ["门禁", "入馆", "flow", "gate"]):
        return "gate_flow", "gate"
    if any(k in fn for k in ["座位", "自习", "seat"]):
        return "seats", "seat"
    if any(k in fn for k in ["研讨", "研修", "seminar", "room"]):
        return "seminar", "room"
    if any(k in fn for k in ["备考", "考研", "考公", "联盟", "exam"]):
        return "exam", "other"
    if any(k in fn for k in ["学者", "导师", "论文", "scholar"]):
        return "scholars", "other"
    return "borrow", "other"


def _validate_filename(filename: str | None) -> str:
    if not filename or "\x00" in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="文件名无效。")
    if filename in {".", ".."} or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="文件名无效。")
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持上传 .xlsx 或 .csv 文件。")
    return filename


def _category_directory(category: str) -> Path:
    if category not in DATA_CATEGORIES:
        raise HTTPException(status_code=400, detail="未知的数据分类。")
    root = IMPORTED_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = (root / category).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=400, detail="数据目录无效。")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def _save_upload(file: UploadFile, category: str) -> tuple[Path, str, int]:
    filename = _validate_filename(file.filename)
    directory = _category_directory(category)
    destination = directory / filename
    if not destination.resolve(strict=False).is_relative_to(directory):
        raise HTTPException(status_code=400, detail="目标路径无效。")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="同名文件已存在，请更换文件名。") from None
    except OSError:
        logger.exception("Could not create uploaded data file")
        raise HTTPException(status_code=500, detail="无法保存上传文件。") from None

    total = 0
    try:
        with os.fdopen(descriptor, "wb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="上传文件不能超过 50 MiB。")
                output.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="上传文件不能为空。")
        return destination, filename, total
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def _process_uploaded_file(category: str, destination: Path) -> Dict[str, Any]:
    try:
        return data_manager.process_file(category, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        logger.exception("Uploaded data file could not be parsed (category=%s)", category)
        raise HTTPException(status_code=422, detail="文件解析失败，请检查格式和内容。") from None


@router.get("/files", response_model=ApiResponse[List[DataFileInfo]])
async def list_data_files():
    """列出已上传或同步的数据文件。"""
    files: List[DataFileInfo] = []
    statuses = data_manager.get_sources_status()
    root = IMPORTED_DIR.resolve()
    for source in statuses:
        if not source.get("is_imported"):
            continue
        category = source.get("id")
        filename = source.get("source_file") or source.get("filename")
        if category not in DATA_CATEGORIES or not filename or Path(filename).name != filename:
            continue
        file_path = root / category / filename
        if not file_path.resolve(strict=False).is_relative_to((root / category).resolve()):
            continue
        size_kb = max(1, round(file_path.stat().st_size / 1024)) if file_path.is_file() else 0
        files.append(
            DataFileInfo(
                id=f"f-{category}",
                filename=filename,
                kind=CATEGORY_KIND_MAP.get(category, "other"),
                rows=source.get("row_count"),
                size_kb=size_kb,
                status="ready",
                uploaded_at=source.get("imported_at") or datetime.now().isoformat(),
                message=source.get("summary") or "已导入。",
            )
        )
    return ApiResponse.ok(data=files)


@router.post("/upload", response_model=ApiResponse[DataFileInfo])
async def upload_general_data_file(file: UploadFile = File(...)):
    """通用数据文件上传并解析。"""
    filename = _validate_filename(file.filename)
    category, kind = guess_category(filename)
    destination, filename, total = await _save_upload(file, category)
    parsed = _process_uploaded_file(category, destination)
    rows = parsed.get("row_count") or parsed.get("total_rows") or parsed.get("rows")
    summary = parsed.get("summary") or f"【{DATA_CATEGORIES[category]['name']}】已成功解析导入"
    info = DataFileInfo(
        id=f"f-{category}-{int(time.time())}",
        filename=filename,
        kind=kind,
        rows=rows,
        size_kb=max(1, round(total / 1024)),
        status="ready",
        uploaded_at=datetime.now().isoformat(),
        message=summary,
    )
    return ApiResponse.ok(data=info, message=f"【{DATA_CATEGORIES[category]['name']}】上传并解析成功！")


@router.get("/sources", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_data_sources():
    """获取 8 类数据的导入状态列表与摘要。"""
    return ApiResponse.ok(data=data_manager.get_sources_status())


@router.post("/upload/{category}", response_model=ApiResponse[Dict[str, Any]])
async def upload_dataset(category: str, file: UploadFile = File(...)):
    """管理员上传指定分类的数据文件。"""
    if category not in DATA_CATEGORIES:
        raise HTTPException(status_code=400, detail="未知的数据分类。")
    destination, _filename, _total = await _save_upload(file, category)
    parsed = _process_uploaded_file(category, destination)
    return ApiResponse.ok(
        data=parsed,
        message=f"【{DATA_CATEGORIES[category]['name']}】上传并解析成功！",
    )


@router.post("/quick-sync/{category}", response_model=ApiResponse[Dict[str, Any]])
async def quick_sync_dataset(category: str):
    """从已配置的数据源目录同步指定分类。"""
    if category not in DATA_CATEGORIES:
        raise HTTPException(status_code=400, detail="未知的数据分类。")
    try:
        meta = data_manager.sync_from_official_source(category)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置的数据源文件不存在。") from None
    except Exception:
        logger.exception("Quick sync failed (category=%s)", category)
        raise HTTPException(status_code=500, detail="数据同步失败。") from None
    return ApiResponse.ok(data=meta, message=f"已同步并解析【{DATA_CATEGORIES[category]['name']}】。")


@router.post("/quick-sync-all", response_model=ApiResponse[Dict[str, Any]])
async def quick_sync_all_datasets():
    """尝试同步全部 8 类数据，并明确报告成功数量。"""
    results = data_manager.sync_all()
    succeeded = sum(1 for result in results.values() if result.get("success"))
    return ApiResponse.ok(
        data=results,
        message=f"同步尝试完成：{succeeded}/{len(results)} 个数据源成功。",
    )
