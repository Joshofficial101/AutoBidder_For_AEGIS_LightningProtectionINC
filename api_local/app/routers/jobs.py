from fastapi import APIRouter, Depends, Path

from app.auth_dependencies import AuthenticatedUser, get_current_user
from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import (
    JobApproveRequest,
    JobApproveResponse,
    JobStatusUpdateRequest,
    JobStatusUpdateResponse,
    JobsBoardResponse,
)
from app.services.jobs_service import (
    approve_and_schedule_job,
    get_jobs_board,
    move_job_to_status,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/board", response_model=JobsBoardResponse, responses=COMMON_ERROR_RESPONSES)
def board(current_user: AuthenticatedUser = Depends(get_current_user)) -> JobsBoardResponse:
    try:
        payload = get_jobs_board(user_id=current_user.user_id)
        return JobsBoardResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOBS_BOARD_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOBS_BOARD_FETCH_FAILED",
            message="Jobs board fetch failed.",
        )


@router.patch(
    "/{job_id}/status",
    response_model=JobStatusUpdateResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def update_status(
    payload: JobStatusUpdateRequest,
    job_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> JobStatusUpdateResponse:
    try:
        start_date = payload.start_date.isoformat() if payload.start_date else None
        completion_date = payload.completion_date.isoformat() if payload.completion_date else None
        invoice_date = payload.invoice_date.isoformat() if payload.invoice_date else None
        result = move_job_to_status(
            job_id=job_id,
            new_status=payload.new_status,
            user_id=current_user.user_id,
            start_date=start_date,
            completion_date=completion_date,
            invoice_date=invoice_date,
            invoice_number=payload.invoice_number,
            assigned_crew=payload.assigned_crew,
            note=payload.note,
        )
        return JobStatusUpdateResponse(**result)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_STATUS_UPDATE_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_STATUS_UPDATE_FAILED",
            message="Job status update failed.",
        )


@router.post(
    "/{job_id}/approve",
    response_model=JobApproveResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def approve_job(
    payload: JobApproveRequest,
    job_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> JobApproveResponse:
    try:
        result = approve_and_schedule_job(
            job_id=job_id,
            user_id=current_user.user_id,
            scheduled_date=payload.scheduled_date.isoformat(),
            assigned_crew=payload.assigned_crew,
            note=payload.note,
        )
        return JobApproveResponse(**result)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_APPROVAL_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_APPROVAL_FAILED",
            message="Job approval failed.",
        )
