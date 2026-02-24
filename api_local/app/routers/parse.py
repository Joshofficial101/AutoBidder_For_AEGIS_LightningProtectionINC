import base64
import binascii
import tempfile
from pathlib import Path

from fastapi import APIRouter

from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import ParsePdfBase64Request, ParsePdfRequest, ParsePdfResponse
from app.services.parsing_service import parse_pdf

router = APIRouter(prefix="/api/v1/parse", tags=["parse"])


@router.post("/pdf", response_model=ParsePdfResponse, responses=COMMON_ERROR_RESPONSES)
def parse_pdf_endpoint(payload: ParsePdfRequest) -> ParsePdfResponse:
    try:
        extracted = parse_pdf(str(payload.pdf_file_path))
        return ParsePdfResponse(extracted=extracted)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="PDF_PARSE_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PDF_PARSE_FAILED",
            message="PDF parse failed.",
        )


@router.post("/pdf/base64", response_model=ParsePdfResponse, responses=COMMON_ERROR_RESPONSES)
def parse_pdf_base64(payload: ParsePdfBase64Request) -> ParsePdfResponse:
    suffix = Path(payload.file_name or "").suffix.lower() or ".pdf"
    temp_path: Path | None = None

    try:
        pdf_bytes = base64.b64decode(payload.file_bytes_base64, validate=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = Path(temp_file.name)

        extracted = parse_pdf(str(temp_path))
        return ParsePdfResponse(extracted=extracted)
    except binascii.Error:
        raise ApiException(
            status_code=400,
            code="INVALID_BASE64",
            message="Invalid base64 PDF payload.",
            detail="file_bytes_base64 must be valid Base64 data.",
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="PDF_PARSE_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="PDF_PARSE_FAILED",
            message="PDF parse failed.",
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
