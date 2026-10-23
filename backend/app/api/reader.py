from typing import List
from fastapi import APIRouter
from app.schemas.common import ApiResponse
from app.schemas.book import BorrowRecord, RenewRequest, RenewResult, ReserveRequest, ReserveResult
from app.agent.tools.data_client import data_client

router = APIRouter(tags=["Reader & Borrow"])

@router.get("/reader/{reader_id}/borrows", response_model=ApiResponse[List[BorrowRecord]])
async def get_reader_borrows(reader_id: str):
    """获取读者在借图书列表"""
    records = data_client.get_user_borrows(reader_id)
    return ApiResponse.ok(data=[BorrowRecord(**r) for r in records])

@router.post("/renew", response_model=ApiResponse[RenewResult])
async def renew_endpoint(req: RenewRequest):
    """办理图书一键续借"""
    res = data_client.renew_book(reader_id=req.reader_id, book_id=req.book_id)
    if not res.get("success"):
        return ApiResponse.fail(code=4001, message=res.get("message", "续借失败"))
    return ApiResponse.ok(
        data=RenewResult(
            new_due_date=res["new_due_date"],
            renew_count=res["renew_count"]
        ),
        message=res.get("message", "续借成功")
    )

@router.post("/reserve", response_model=ApiResponse[ReserveResult])
async def reserve_endpoint(req: ReserveRequest):
    """在线预约图书"""
    res = data_client.reserve_book(reader_id=req.reader_id, isbn=req.isbn)
    return ApiResponse.ok(
        data=ReserveResult(
            queue_position=res["queue_position"],
            notify_channel=res["notify_channel"]
        ),
        message=res.get("message", "预约成功")
    )
