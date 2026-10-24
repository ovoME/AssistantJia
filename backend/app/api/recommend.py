from typing import List, Optional
from fastapi import APIRouter, Query, Depends
from app.schemas.common import ApiResponse
from app.schemas.book import RecommendBook
from app.schemas.admin import BookStat
from app.agent.tools.data_client import data_client
from app.services.local_data import borrowing
from app.auth import reader_identity, resolve_reader

router = APIRouter(tags=["Recommendation"])

@router.get("/recommend", response_model=ApiResponse[List[RecommendBook]])
async def recommend_endpoint(
    reader_id: Optional[str] = Query(None, description="读者证件号"),
    limit: int = Query(5, ge=1, le=20, description="推荐数量"),
    identity: Optional[str] = Depends(reader_identity)
):
    """获取个性化推荐书单"""
    reader = resolve_reader(reader_id, identity)
    service = borrowing()
    recs = service.engine.recommend(reader, limit)
    return ApiResponse.ok(data=[RecommendBook(**r) for r in recs], **service.metadata())

@router.get("/hot-books", response_model=ApiResponse[List[BookStat]])
async def hot_books_endpoint(
    category: Optional[str] = Query(None, description="中图分类大类，如 I、TP"),
    limit: int = Query(10, ge=1, le=50, description="榜单数量")
):
    """获取全馆借阅热门榜单（按借阅量倒序，category 过滤生效）"""
    service = borrowing()
    books = service.engine.hot_books(category, limit)
    return ApiResponse.ok(data=[BookStat(**b) for b in books], **service.metadata())
