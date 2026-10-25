from typing import List
from fastapi import APIRouter, Depends, Query
from app.auth import require_admin
from app.schemas.common import ApiResponse
from app.schemas.admin import AdminSummary, CategoryStat, BookStat, PublisherStat, PurchaseAdviceRequest, BookReviewRequest
from app.services.local_data import borrowing, usage

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"], dependencies=[Depends(require_admin)])


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
