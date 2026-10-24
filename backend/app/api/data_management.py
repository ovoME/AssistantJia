from typing import List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.schemas.common import ApiResponse
from app.services.data_manager import data_manager, DATA_CATEGORIES, IMPORTED_DIR

router = APIRouter(prefix="/admin/data", tags=["Admin Data Management"])


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
