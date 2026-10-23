from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.common import ApiResponse
from app.schemas.book import Book
from app.agent.tools.data_client import data_client

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("/search", response_model=ApiResponse[List[Book]])
async def search_books_endpoint(
    query: str = Query("", description="书名/作者/索书号/关键词"),
    limit: int = Query(5, ge=1, le=20, description="返回条数")
):
    """馆藏图书与架位检索"""
    results = data_client.search_books_opac(query=query, limit=limit)
    books = [Book(**b) for b in results]
    return ApiResponse.ok(data=books)

@router.get("/{isbn}", response_model=ApiResponse[Optional[Book]])
async def get_book_by_isbn(isbn: str):
    """根据 ISBN 获取图书详情与当前在馆状态"""
    results = data_client.search_books_opac(query=isbn, limit=1)
    if results:
        return ApiResponse.ok(data=Book(**results[0]))
    return ApiResponse.fail(code=4004, message="未找到该图书")
