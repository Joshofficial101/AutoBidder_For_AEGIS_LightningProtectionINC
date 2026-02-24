import base64
import binascii
import tempfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import BidPreviewBase64Request, BidPreviewRequest, BidPreviewResponse
from app.services.bidding_service import export_bid_excel, export_bid_pdf, preview_bid

router = APIRouter(prefix="/api/v1/bids", tags=["bids"])


def _safe_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_"}:
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    normalized = "".join(keep).strip("_")
    return normalized[:80] or "lightningbid_bid"


def _download_response(file_path: Path, filename: str, media_type: str) -> Response:
    content = file_path.read_bytes()
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_payload_from_preview_request(payload: BidPreviewRequest) -> dict:
    preview_payload = payload.model_dump()
    preview_payload["pricing_file_path"] = str(payload.pricing_file_path)
    preview_payload["compliance_code"] = payload.compliance_code.value
    return preview_payload


def _build_payload_from_base64_request(payload: BidPreviewBase64Request, pricing_temp_path: Path) -> dict:
    return {
        "pricing_file_path": str(pricing_temp_path),
        "pricing_sheet": payload.pricing_sheet,
        "compliance_code": payload.compliance_code.value,
        "project_data": payload.project_data,
        "workers": [worker.model_dump() for worker in payload.workers],
    }


@router.post(
    "/preview",
    response_model=BidPreviewResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def preview(payload: BidPreviewRequest) -> BidPreviewResponse:
    try:
        preview_payload = _build_payload_from_preview_request(payload)
        result = preview_bid(preview_payload)
        return BidPreviewResponse(**result)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_PREVIEW_FAILED",
            message="Bid preview failed.",
        )


@router.post(
    "/preview/base64",
    response_model=BidPreviewResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def preview_base64(payload: BidPreviewBase64Request) -> BidPreviewResponse:
    temp_path: Path | None = None

    try:
        pricing_bytes = base64.b64decode(payload.pricing_file_base64, validate=True)
        suffix = Path(payload.file_name or "").suffix.lower() or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(pricing_bytes)
            temp_path = Path(temp_file.name)

        preview_payload = _build_payload_from_base64_request(payload, temp_path)

        result = preview_bid(preview_payload)
        return BidPreviewResponse(**result)
    except binascii.Error:
        raise ApiException(
            status_code=400,
            code="INVALID_BASE64",
            message="Invalid base64 pricing payload.",
            detail="pricing_file_base64 must be valid Base64 data.",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_PREVIEW_FAILED",
            message="Bid preview failed.",
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.post("/export/excel", responses=COMMON_ERROR_RESPONSES)
def export_excel(payload: BidPreviewRequest) -> Response:
    output_path: Path | None = None
    try:
        request_payload = _build_payload_from_preview_request(payload)
        project_name = str(request_payload.get("project_data", {}).get("project_name") or "lightningbid_bid")
        safe_name = _safe_name(project_name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as output_file:
            output_path = Path(output_file.name)

        export_bid_excel(request_payload, output_path)
        return _download_response(
            output_path,
            f"{safe_name}_bid.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_EXPORT_FAILED",
            message="Excel export failed.",
        )
    finally:
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)


@router.post("/export/excel/base64", responses=COMMON_ERROR_RESPONSES)
def export_excel_base64(payload: BidPreviewBase64Request) -> Response:
    pricing_path: Path | None = None
    output_path: Path | None = None
    try:
        pricing_bytes = base64.b64decode(payload.pricing_file_base64, validate=True)
        suffix = Path(payload.file_name or "").suffix.lower() or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(pricing_bytes)
            pricing_path = Path(temp_file.name)
        request_payload = _build_payload_from_base64_request(payload, pricing_path)
        project_name = str(request_payload.get("project_data", {}).get("project_name") or "lightningbid_bid")
        safe_name = _safe_name(project_name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as output_file:
            output_path = Path(output_file.name)

        export_bid_excel(request_payload, output_path)
        return _download_response(
            output_path,
            f"{safe_name}_bid.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except binascii.Error:
        raise ApiException(
            status_code=400,
            code="INVALID_BASE64",
            message="Invalid base64 pricing payload.",
            detail="pricing_file_base64 must be valid Base64 data.",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_EXPORT_FAILED",
            message="Excel export failed.",
        )
    finally:
        if pricing_path and pricing_path.exists():
            pricing_path.unlink(missing_ok=True)
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)


@router.post("/export/pdf", responses=COMMON_ERROR_RESPONSES)
def export_pdf(payload: BidPreviewRequest) -> Response:
    output_path: Path | None = None
    try:
        request_payload = _build_payload_from_preview_request(payload)
        project_name = str(request_payload.get("project_data", {}).get("project_name") or "lightningbid_bid")
        safe_name = _safe_name(project_name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as output_file:
            output_path = Path(output_file.name)

        export_bid_pdf(request_payload, output_path)
        return _download_response(
            output_path,
            f"{safe_name}_submittal.pdf",
            "application/pdf",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_EXPORT_FAILED",
            message="PDF export failed.",
        )
    finally:
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)


@router.post("/export/pdf/base64", responses=COMMON_ERROR_RESPONSES)
def export_pdf_base64(payload: BidPreviewBase64Request) -> Response:
    pricing_path: Path | None = None
    output_path: Path | None = None
    try:
        pricing_bytes = base64.b64decode(payload.pricing_file_base64, validate=True)
        suffix = Path(payload.file_name or "").suffix.lower() or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(pricing_bytes)
            pricing_path = Path(temp_file.name)
        request_payload = _build_payload_from_base64_request(payload, pricing_path)
        project_name = str(request_payload.get("project_data", {}).get("project_name") or "lightningbid_bid")
        safe_name = _safe_name(project_name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as output_file:
            output_path = Path(output_file.name)

        export_bid_pdf(request_payload, output_path)
        return _download_response(
            output_path,
            f"{safe_name}_submittal.pdf",
            "application/pdf",
        )
    except binascii.Error:
        raise ApiException(
            status_code=400,
            code="INVALID_BASE64",
            message="Invalid base64 pricing payload.",
            detail="pricing_file_base64 must be valid Base64 data.",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="BID_EXPORT_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="BID_EXPORT_FAILED",
            message="PDF export failed.",
        )
    finally:
        if pricing_path and pricing_path.exists():
            pricing_path.unlink(missing_ok=True)
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)
