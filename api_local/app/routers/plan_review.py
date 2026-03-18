import base64
import binascii
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.auth_dependencies import AuthenticatedUser, get_current_user
from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.file_limits import PayloadTooLargeError, assert_pdf_base64_within_limit
from app.schemas import (
    PlanReviewBase64Request,
    PlanReviewRequest,
    PlanReviewResponse,
    PlanReviewSaveRequest,
    PlanReviewSaveResponse,
)
from app.services.plan_review_service import generate_plan_review, load_plan_review, save_plan_review
from app.temp_files import safe_unlink

router = APIRouter(
    prefix="/api/v1/plan-review",
    tags=["plan-review"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/generate", response_model=PlanReviewResponse, responses=COMMON_ERROR_RESPONSES)
def generate(payload: PlanReviewRequest) -> PlanReviewResponse:
    try:
        result = generate_plan_review(
            project_data=payload.project_data,
            compliance_code=payload.compliance_code.value,
            pdf_file_path=str(payload.pdf_file_path) if payload.pdf_file_path else None,
        )
        return PlanReviewResponse(**result)
    except PayloadTooLargeError as exc:
        raise ApiException(
            status_code=413,
            code="PAYLOAD_TOO_LARGE",
            message=str(exc),
            detail=str(exc),
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="PLAN_REVIEW_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PLAN_REVIEW_FAILED",
            message="Plan review generation failed.",
        )


@router.post("/generate/base64", response_model=PlanReviewResponse, responses=COMMON_ERROR_RESPONSES)
def generate_base64(payload: PlanReviewBase64Request) -> PlanReviewResponse:
    suffix = Path(payload.file_name or "").suffix.lower() or ".pdf"
    temp_path: Path | None = None

    try:
        assert_pdf_base64_within_limit(payload.file_bytes_base64)
        pdf_bytes = base64.b64decode(payload.file_bytes_base64, validate=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = Path(temp_file.name)

        result = generate_plan_review(
            project_data=payload.project_data,
            compliance_code=payload.compliance_code.value,
            pdf_file_path=str(temp_path),
        )
        if payload.file_name:
            result["source_file_name"] = payload.file_name
        return PlanReviewResponse(**result)
    except binascii.Error:
        raise ApiException(
            status_code=400,
            code="INVALID_BASE64",
            message="Invalid base64 PDF payload.",
            detail="file_bytes_base64 must be valid Base64 data.",
        )
    except PayloadTooLargeError as exc:
        raise ApiException(
            status_code=413,
            code="PAYLOAD_TOO_LARGE",
            message=str(exc),
            detail=str(exc),
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="PLAN_REVIEW_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PLAN_REVIEW_FAILED",
            message="Plan review generation failed.",
        )
    finally:
        safe_unlink(temp_path)


@router.post("/save", response_model=PlanReviewSaveResponse, responses=COMMON_ERROR_RESPONSES)
def save(
    payload: PlanReviewSaveRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PlanReviewSaveResponse:
    try:
        result = save_plan_review(
            user_id=current_user.user_id,
            project_name=payload.project_name,
            project_data=payload.project_data,
            plan_review=payload.plan_review.model_dump(),
            compliance_code=payload.compliance_code.value,
        )
        return PlanReviewSaveResponse(**result)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="PLAN_REVIEW_SAVE_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PLAN_REVIEW_SAVE_FAILED",
            message="Work plan save failed.",
        )


@router.get("/load", response_model=PlanReviewResponse, responses=COMMON_ERROR_RESPONSES)
def load(
    project_name: str = Query(..., min_length=1, max_length=160),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PlanReviewResponse:
    try:
        result = load_plan_review(user_id=current_user.user_id, project_name=project_name)
        return PlanReviewResponse(**result)
    except ValueError as exc:
        raise ApiException(
            status_code=404,
            code="PLAN_REVIEW_NOT_FOUND",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PLAN_REVIEW_LOAD_FAILED",
            message="Work plan load failed.",
        )
