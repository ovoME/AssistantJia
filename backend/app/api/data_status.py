from fastapi import APIRouter
from app.config import settings
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Data Sources"])


@router.get("/data/status", response_model=ApiResponse[dict])
def data_status():
    return ApiResponse.ok(data={"catalog": "synthetic_fixture" if settings.DATA_PROFILE == "integration" else "static_snapshot", "recommendations": "historical_sample",
                              "rules": "official_summary", "business": "integration_demo" if settings.DATA_PROFILE == "integration" else settings.OPAC_PROVIDER,
                              "data_profile": settings.DATA_PROFILE,
                              "personalization_requires_auth": True, "admin_requires_auth": True}, is_live=False)
