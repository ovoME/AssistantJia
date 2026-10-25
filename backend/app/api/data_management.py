import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.schemas.common import ApiResponse
from app.schemas.admin import DataFileInfo
from app.services.data_manager import data_manager, DATA_CATEGORIES, IMPORTED_DIR

router = APIRouter(prefix="/admin/data", tags=["Admin Data Management"])

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
    """根据文件名自动推断所属业务类别及前端 kind"""
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


@router.get("/files", response_model=ApiResponse[List[DataFileInfo]])
async def list_data_files():
    """列出已上传/已同步的数据文件列表（契约对齐前端 PR #20 DataManageView）"""
    files: List[DataFileInfo] = []
    statuses = data_manager.get_sources_status()
    for s in statuses:
        if not s.get("is_imported"):
            continue
        cat_id = s["id"]
        source_file = s.get("source_file") or s.get("filename")
        file_path = IMPORTED_DIR / cat_id / source_file
        size_kb = 0
        if file_path.exists():
            size_kb = max(1, round(file_path.stat().st_size / 1024))
        kind = CATEGORY_KIND_MAP.get(cat_id, "other")

        uploaded_at = s.get("imported_at")
        if uploaded_at:
            try:
                dt = datetime.strptime(uploaded_at, "%Y-%m-%d %H:%M:%S")
                uploaded_at = dt.isoformat()
            except Exception:
                pass
        else:
            uploaded_at = datetime.now().isoformat()

        files.append(
            DataFileInfo(
                id=f"f-{cat_id}",
                filename=source_file,
                kind=kind,
                rows=s.get("row_count"),
                size_kb=size_kb,
                status="ready",
                uploaded_at=uploaded_at,
                message=s.get("summary") or f"已入库：{s.get('row_count', 0):,} 条记录",
            )
        )
    return ApiResponse.ok(data=files)


@router.post("/upload", response_model=ApiResponse[DataFileInfo])
async def upload_general_data_file(file: UploadFile = File(...)):
    """通用数据文件上传（支持拖拽上传与自动分类解析，对接前端 PR #20）"""
    filename = file.filename or "uploaded_data"
    suffix = Path(filename).suffix.lower()
    if suffix not in [".xlsx", ".csv"]:
        return ApiResponse.fail(code=4000, message="仅支持上传 .xlsx 或 .csv 格式的数据文件")

    category, kind = guess_category(filename)
    dest_dir = IMPORTED_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    content = await file.read()
    dest_file.write_bytes(content)
    size_kb = max(1, round(len(content) / 1024))

    try:
        parsed_meta = data_manager.process_file(category, dest_file)
        rows = parsed_meta.get("row_count") or parsed_meta.get("total_rows") or parsed_meta.get("rows")
        summary = parsed_meta.get("summary") or f"【{DATA_CATEGORIES[category]['name']}】已成功解析导入"

        info = DataFileInfo(
            id=f"f-{category}-{int(time.time())}",
            filename=filename,
            kind=kind,
            rows=rows,
            size_kb=size_kb,
            status="ready",
            uploaded_at=datetime.now().isoformat(),
            message=summary,
        )
        return ApiResponse.ok(data=info, message=f"【{DATA_CATEGORIES[category]['name']}】上传并解析成功！")
    except Exception as e:
        info = DataFileInfo(
            id=f"f-err-{int(time.time())}",
            filename=filename,
            kind=kind,
            rows=None,
            size_kb=size_kb,
            status="error",
            uploaded_at=datetime.now().isoformat(),
            message=f"解析失败: {str(e)}",
        )
        return ApiResponse.fail(code=5000, message=f"数据解析失败: {str(e)}", data=info)


@router.get("/sources", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_data_sources():
    """获取 8 大多源数据的导入状态列表与摘要"""
    status_list = data_manager.get_sources_status()
    return ApiResponse.ok(data=status_list)


@router.post("/upload/{category}", response_model=ApiResponse[Dict[str, Any]])
async def upload_dataset(
    category: str,
    file: UploadFile = File(...)
):
    """管理员上传指定分类的数据文件 (支持 .xlsx / .csv)"""
    if category not in DATA_CATEGORIES:
        return ApiResponse.fail(code=4000, message=f"未知的数据分类标识: {category}")

    filename = file.filename or "upload_file"
    suffix = Path(filename).suffix.lower()
    if suffix not in [".xlsx", ".csv"]:
        return ApiResponse.fail(code=4000, message="仅支持上传 .xlsx 或 .csv 格式的数据文件")

    dest_dir = IMPORTED_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    content = await file.read()
    dest_file.write_bytes(content)

    try:
        parsed_meta = data_manager.process_file(category, dest_file)
        return ApiResponse.ok(data=parsed_meta, message=f"【{DATA_CATEGORIES[category]['name']}】上传并解析成功！")
    except Exception as e:
        return ApiResponse.fail(code=5000, message=f"数据解析失败: {str(e)}")


@router.post("/quick-sync/{category}", response_model=ApiResponse[Dict[str, Any]])
async def quick_sync_dataset(category: str):
    """一键从官方比赛目录自动载入指定分类的数据"""
    if category not in DATA_CATEGORIES:
        return ApiResponse.fail(code=4000, message=f"未知分类: {category}")
    try:
        meta = data_manager.sync_from_official_source(category)
        return ApiResponse.ok(data=meta, message=f"已成功一键同步并解析【{DATA_CATEGORIES[category]['name']}】！")
    except Exception as e:
        return ApiResponse.fail(code=5000, message=f"同步失败: {str(e)}")


@router.post("/quick-sync-all", response_model=ApiResponse[Dict[str, Any]])
async def quick_sync_all_datasets():
    """一键全量导入 8 项官方比赛数据集"""
    results = data_manager.sync_all()
    return ApiResponse.ok(data=results, message="全量 8 项官方大数据集同步解析完成！")
