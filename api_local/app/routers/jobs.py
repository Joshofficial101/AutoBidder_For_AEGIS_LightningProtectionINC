from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import FileResponse, Response

from app.auth_dependencies import AuthenticatedUser, get_current_user
from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import (
    JobAssetDetailResponse,
    JobExportCleanupResponse,
    JobAssetsIndexResponse,
    JobApproveRequest,
    JobApproveResponse,
    JobStatusUpdateRequest,
    JobStatusUpdateResponse,
    JobsBoardResponse,
)
from app.services.jobs_service import (
    approve_and_schedule_job,
    cleanup_job_exports,
    export_job_excel,
    export_job_pdf,
    get_historical_job_export,
    get_job_asset_detail,
    get_job_assets_index,
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


@router.get("/assets", response_model=JobAssetsIndexResponse, responses=COMMON_ERROR_RESPONSES)
def assets_index(current_user: AuthenticatedUser = Depends(get_current_user)) -> JobAssetsIndexResponse:
    try:
        payload = get_job_assets_index(user_id=current_user.user_id)
        return JobAssetsIndexResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_ASSETS_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_ASSETS_FETCH_FAILED",
            message="Job assets fetch failed.",
        )


@router.get(
    "/{job_id}/assets",
    response_model=JobAssetDetailResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def asset_detail(
    job_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> JobAssetDetailResponse:
    try:
        payload = get_job_asset_detail(user_id=current_user.user_id, job_id=job_id)
        return JobAssetDetailResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_ASSET_DETAIL_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_ASSET_DETAIL_FETCH_FAILED",
            message="Job asset detail fetch failed.",
        )


@router.get("/{job_id}/export/excel", responses=COMMON_ERROR_RESPONSES)
def job_export_excel(
    job_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        output_path = export_job_excel(job_id=job_id, user_id=current_user.user_id)
        return FileResponse(
            path=output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=output_path.name,
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_EXPORT_FAILED",
            message="Job Excel export failed.",
        )


@router.get("/{job_id}/export/pdf", responses=COMMON_ERROR_RESPONSES)
def job_export_pdf(
    job_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        output_path = export_job_pdf(job_id=job_id, user_id=current_user.user_id)
        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=output_path.name,
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_EXPORT_FAILED",
            message="Job PDF export failed.",
        )


@router.get("/{job_id}/exports/{export_id}/download", responses=COMMON_ERROR_RESPONSES)
def download_job_export_history(
    job_id: int = Path(..., ge=1),
    export_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        payload = get_historical_job_export(job_id=job_id, user_id=current_user.user_id, export_id=export_id)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if payload["export_type"] == "excel"
            else "application/pdf"
        )
        return FileResponse(
            path=payload["file_path"],
            media_type=media_type,
            filename=payload["file_name"],
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_EXPORT_HISTORY_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_EXPORT_HISTORY_FAILED",
            message="Job export history download failed.",
        )


@router.post(
    "/{job_id}/exports/cleanup",
    response_model=JobExportCleanupResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def cleanup_exports(
    job_id: int = Path(..., ge=1),
    older_than_days: int = Query(90, ge=1, le=3650),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> JobExportCleanupResponse:
    try:
        payload = cleanup_job_exports(
            job_id=job_id,
            user_id=current_user.user_id,
            older_than_days=older_than_days,
        )
        return JobExportCleanupResponse(**payload)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="JOB_EXPORT_CLEANUP_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="JOB_EXPORT_CLEANUP_FAILED",
            message="Job export cleanup failed.",
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
