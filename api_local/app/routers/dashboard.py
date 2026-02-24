from typing import Optional

from fastapi import APIRouter, Query

from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import DashboardSummaryResponse
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse, responses=COMMON_ERROR_RESPONSES)
def summary(user_id: Optional[int] = Query(default=None, ge=1)) -> DashboardSummaryResponse:
    try:
        payload = get_dashboard_summary(user_id=user_id)
        return DashboardSummaryResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="DASHBOARD_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="DASHBOARD_FETCH_FAILED",
            message="Dashboard summary failed.",
        )
