from typing import List
from fastapi import APIRouter, Depends
from app.auth import reader_identity, resolve_reader
from app.config import settings
from app.schemas.common import ApiResponse
from app.schemas.book import BorrowRecord, RenewRequest, RenewResult, ReserveRequest, ReserveResult
from app.services.local_data import provider

router = APIRouter(tags=["Reader & Borrow"])


def authorized(reader_id, identity):
    if reader_id == "me":
        if identity is None:
            from fastapi import HTTPException
            raise HTTPException(401, "请先取得本人读者凭证。")
        return identity
    if settings.OPAC_PROVIDER == "demo" and reader_id == "demo-reader" and identity is None:
        return reader_id
    return resolve_reader(reader_id, identity)


def metadata():
    demo = settings.OPAC_PROVIDER == "demo" or settings.DATA_PROFILE == "integration"
    return {"dataset_label": "simulated" if demo else "unknown", "is_live": False,
            "scope": "demo_business" if demo else "unavailable"}


@router.get("/reader/{reader_id}/borrows", response_model=ApiResponse[List[BorrowRecord]])
def get_reader_borrows(reader_id: str, identity=Depends(reader_identity)):
    reader = authorized(reader_id, identity)
    return ApiResponse.ok(data=provider().current_borrows(reader), **metadata())


@router.post("/renew", response_model=ApiResponse[RenewResult])
def renew_endpoint(req: RenewRequest, identity=Depends(reader_identity)):
    reader = authorized(req.reader_id, identity)
    result = provider().renew(reader, req.book_id)
    if not result.get("success"):
        return ApiResponse.fail(code=result.get("code", 4001), message=result["message"])
    return ApiResponse.ok(data=RenewResult(**result), message=result["message"], **metadata())


@router.post("/reserve", response_model=ApiResponse[ReserveResult])
def reserve_endpoint(req: ReserveRequest, identity=Depends(reader_identity)):
    reader = authorized(req.reader_id, identity)
    result = provider().reserve(reader, req.isbn)
    if not result.get("success"):
        return ApiResponse.fail(code=result.get("code", 4002), message=result["message"])
    return ApiResponse.ok(data=ReserveResult(**result), message=result["message"], **metadata())
