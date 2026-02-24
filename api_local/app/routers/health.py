from datetime import datetime, timezone

from fastapi import APIRouter, Response

from app.schemas import HealthReadinessResponse, HealthResponse
from app.services.health_service import build_readiness_report

router = APIRouter(tags=["health"])
STARTED_AT = datetime.now(timezone.utc)
APP_VERSION = "1.0.0"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthReadinessResponse)
def health_ready(response: Response) -> HealthReadinessResponse:
    report = build_readiness_report(started_at=STARTED_AT, app_version=APP_VERSION)
    if not report["ready"]:
        response.status_code = 503
    return HealthReadinessResponse(**report)
