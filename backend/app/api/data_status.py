from fastapi import APIRouter
from app.config import settings
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Data Sources"])


@router.get("/data/status", response_model=ApiResponse[dict])
def data_status():
    return ApiResponse.ok(data={"catalog": "static_snapshot", "recommendations": "historical_sample",
                              "rules": "official_summary", "business": settings.OPAC_PROVIDER,
                              "personalization_requires_auth": True, "admin_requires_auth": True}, is_live=False)
