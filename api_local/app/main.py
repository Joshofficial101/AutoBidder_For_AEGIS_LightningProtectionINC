import logging
import sys
from time import perf_counter
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.correlation import get_correlation_id, reset_correlation_id, set_correlation_id
from app.errors import ApiException, build_error_response, coerce_http_exception
from app.logging_config import configure_structured_logging
from app.routers.health import router as health_router
from app.routers.bids import router as bids_router
from app.routers.parse import router as parse_router
from app.routers.dashboard import router as dashboard_router
from app.routers.jobs import router as jobs_router
from app.routers.calendar import router as calendar_router
from app.routers.auth import router as auth_router
from app.schemas import RootResponse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db_connector import DBConnector

logger = logging.getLogger("lightningbid.api")
CORRELATION_HEADER = "X-Correlation-ID"

app = FastAPI(
    title="LightningBid Local API",
    version="1.0.0",
    description="Local FastAPI backend for desktop React+Tauri client",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# Desktop app + local dev frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(bids_router)
app.include_router(parse_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(calendar_router)
app.include_router(auth_router)


def _attach_correlation_header(request: Request, headers: dict | None = None) -> dict:
    merged_headers = dict(headers or {})
    correlation_id = getattr(request.state, "correlation_id", None) or get_correlation_id()
    if correlation_id and CORRELATION_HEADER not in merged_headers:
        merged_headers[CORRELATION_HEADER] = correlation_id
    return merged_headers


@app.middleware("http")
async def correlation_and_request_logging(request: Request, call_next):
    incoming_id = request.headers.get(CORRELATION_HEADER) or request.headers.get("X-Request-ID")
    correlation_id = incoming_id.strip() if incoming_id else uuid4().hex
    token = set_correlation_id(correlation_id)
    request.state.correlation_id = correlation_id
    started = perf_counter()
    client_ip = request.client.host if request.client else None

    logger.info(
        "request.started",
        extra={
            "event": "request.started",
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
        },
    )

    try:
        response = await call_next(request)
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        reset_correlation_id(token)

    response.headers[CORRELATION_HEADER] = correlation_id
    logger.info(
        "request.completed",
        extra={
            "event": "request.completed",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "correlation_id": correlation_id,
        },
    )
    return response


@app.on_event("startup")
def startup_database_maintenance() -> None:
    configure_structured_logging()
    logger.info("api.startup", extra={"event": "api.startup"})
    db = DBConnector()
    db.close()


@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException):
    logger.warning(
        "api.exception",
        extra={
            "event": "api.exception",
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        errors=exc.errors,
        headers=_attach_correlation_header(request, dict(exc.headers or {})),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    validation_errors = exc.errors()
    oversized_base64_fields = {"pricing_file_base64", "file_bytes_base64"}
    has_payload_too_large_error = any(
        (error.get("type") == "string_too_long")
        and any(str(part) in oversized_base64_fields for part in error.get("loc", []))
        for error in validation_errors
    )

    status_code = 413 if has_payload_too_large_error else 422
    error_code = "PAYLOAD_TOO_LARGE" if has_payload_too_large_error else "VALIDATION_ERROR"
    detail = (
        "Request payload exceeded configured size limits."
        if has_payload_too_large_error
        else "One or more fields are invalid."
    )
    message = (
        "Request payload too large."
        if has_payload_too_large_error
        else "Request validation failed."
    )

    logger.warning(
        "request.validation_error",
        extra={
            "event": "request.validation_error",
            "error_code": error_code,
            "status_code": status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    return build_error_response(
        status_code=status_code,
        code=error_code,
        message=message,
        detail=detail,
        errors=validation_errors,
        headers=_attach_correlation_header(request),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "http.exception",
        extra={
            "event": "http.exception",
            "error_code": f"HTTP_{exc.status_code}",
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    payload = coerce_http_exception(exc)
    payload.headers.update(_attach_correlation_header(request, dict(payload.headers or {})))
    return payload


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled.exception",
        extra={
            "event": "unhandled.exception",
            "error_code": "INTERNAL_ERROR",
            "status_code": 500,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=exc,
    )
    return build_error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected server error occurred.",
        detail="See server logs for details.",
        headers=_attach_correlation_header(request),
    )


@app.get("/", tags=["root"], response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service="lightningbid-local-api",
        status="ok",
        api_version="v1",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )
