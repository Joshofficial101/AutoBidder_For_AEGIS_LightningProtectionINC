from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.schemas import ApiError


@dataclass(slots=True)
class ApiException(Exception):
    status_code: int
    code: str
    message: str
    detail: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Mapping[str, str]] = None


COMMON_ERROR_RESPONSES = {
    400: {"model": ApiError, "description": "Bad request"},
    404: {"model": ApiError, "description": "Not found"},
    409: {"model": ApiError, "description": "Conflict"},
    422: {"model": ApiError, "description": "Validation error"},
    429: {"model": ApiError, "description": "Rate limited"},
    500: {"model": ApiError, "description": "Internal server error"},
}


def status_to_error_code(status_code: int) -> str:
    if status_code == 400:
        return "BAD_REQUEST"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 429:
        return "RATE_LIMITED"
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "REQUEST_ERROR"


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: Optional[str] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> JSONResponse:
    body = ApiError(code=code, message=message, detail=detail, errors=errors)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=dict(headers or {}),
    )


def coerce_http_exception(exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or status_to_error_code(exc.status_code))
        message = str(detail.get("message") or detail.get("detail") or "Request failed.")
        detail_text = detail.get("detail")
        errors = detail.get("errors")
        if not isinstance(detail_text, str):
            detail_text = None
        if not isinstance(errors, list):
            errors = None
        return build_error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            detail=detail_text,
            errors=errors,
            headers=exc.headers,
        )

    message = str(detail) if detail else "Request failed."
    return build_error_response(
        status_code=exc.status_code,
        code=status_to_error_code(exc.status_code),
        message=message,
        detail=message,
        headers=exc.headers,
    )
