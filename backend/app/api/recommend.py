from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.common import ApiResponse
from app.schemas.book import RecommendBook
from app.schemas.admin import BookStat
from app.agent.tools.data_client import data_client

router = APIRouter(tags=["Recommendation"])

@router.get("/recommend", response_model=ApiResponse[List[RecommendBook]])
async def recommend_endpoint(
    reader_id: Optional[str] = Query(None, description="读者证件号"),
    limit: int = Query(5, ge=1, le=20, description="推荐数量")
):
    """获取个性化推荐书单"""
    recs = data_client.get_recommendations(reader_id=reader_id, limit=limit)
    return ApiResponse.ok(data=[RecommendBook(**r) for r in recs])

@router.get("/hot-books", response_model=ApiResponse[List[BookStat]])
async def hot_books_endpoint(
    category: Optional[str] = Query(None, description="中图分类大类，如 I、TP"),
    limit: int = Query(10, ge=1, le=50, description="榜单数量")
):
    """获取全馆借阅热门榜单（按借阅量倒序，category 过滤生效）"""
    books = data_client.get_hot_books(category=category, limit=limit)
    return ApiResponse.ok(data=[BookStat(**b) for b in books])
