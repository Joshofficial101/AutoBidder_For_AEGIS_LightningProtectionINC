from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import CalendarDayResponse, CalendarJobsResponse, CalendarStatusFilter
from app.services.calendar_service import get_calendar_day, get_calendar_jobs

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.get("/jobs", response_model=CalendarJobsResponse, responses=COMMON_ERROR_RESPONSES)
def calendar_jobs(
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date: date = Query(..., description="YYYY-MM-DD"),
    user_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[CalendarStatusFilter] = Query(default=None),
    crew: Optional[str] = Query(default=None),
) -> CalendarJobsResponse:
    try:
        normalized_status: Optional[str] = None
        if status and status != CalendarStatusFilter.ALL:
            normalized_status = status.value

        payload = get_calendar_jobs(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            user_id=user_id,
            status=normalized_status,
            crew=crew,
        )
        return CalendarJobsResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="CALENDAR_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="CALENDAR_FETCH_FAILED",
            message="Calendar jobs lookup failed.",
        )


@router.get("/day", response_model=CalendarDayResponse, responses=COMMON_ERROR_RESPONSES)
def calendar_day(
    date: date = Query(..., description="YYYY-MM-DD"),
    user_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[CalendarStatusFilter] = Query(default=None),
    crew: Optional[str] = Query(default=None),
) -> CalendarDayResponse:
    try:
        normalized_status: Optional[str] = None
        if status and status != CalendarStatusFilter.ALL:
            normalized_status = status.value

        payload = get_calendar_day(
            target_date=date.isoformat(),
            user_id=user_id,
            status=normalized_status,
            crew=crew,
        )
        return CalendarDayResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="CALENDAR_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="CALENDAR_FETCH_FAILED",
            message="Calendar day lookup failed.",
        )
