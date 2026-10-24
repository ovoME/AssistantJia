from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.common import ApiResponse
from app.schemas.book import Book
from app.agent.tools.data_client import data_client
from app.services.local_data import catalog, provider
from app.config import settings

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("/search", response_model=ApiResponse[List[Book]])
async def search_books_endpoint(
    query: str = Query("", description="书名/作者/索书号/关键词"),
    limit: int = Query(5, ge=1, le=20, description="返回条数")
):
    """馆藏图书与架位检索"""
    source = catalog()
    payload = source.response(query, limit)
    label = payload["dataset_label"]
    books = [Book(**{**row, "dataset_label": label}) for row in payload["data"]]
    return ApiResponse.ok(data=books, **{key: payload[key] for key in
                          ("dataset_label", "scope", "built_at", "is_live", "limitations")})


@router.get("/holdings/{book_key}", response_model=ApiResponse[dict])
def get_holdings(book_key: str):
    """预留馆方馆藏入口；demo 明确为模拟状态。"""
    return ApiResponse.ok(data=provider().holdings(book_key), dataset_label="simulated", is_live=False)

@router.get("/{isbn}", response_model=ApiResponse[Optional[Book]])
async def get_book_by_isbn(isbn: str):
    """根据 ISBN 获取图书详情与当前在馆状态"""
    source = catalog()
    results = source.lookup_isbn(isbn)
    if results:
        return ApiResponse.ok(data=Book(**results[0]))
    return ApiResponse.fail(code=4004, message="未找到该图书")
