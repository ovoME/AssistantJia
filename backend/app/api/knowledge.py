from fastapi import APIRouter, Query
from app.schemas.common import ApiResponse
from app.services.local_data import knowledge

router = APIRouter(prefix="/knowledge", tags=["Library Rules"])


@router.get("/search", response_model=ApiResponse[dict])
def search_rules(question: str = Query(..., min_length=1, max_length=500)):
    return ApiResponse.ok(data=knowledge().answer(question), dataset_label="official_summary", is_live=False,
                          scope="library_rules_snapshot")
