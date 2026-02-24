from fastapi import APIRouter

from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import AuthUserResponse, LoginRequest, RegisterRequest, ResetPasswordBackupRequest
from app.services.auth_service import (
    AuthLockoutError,
    login_user,
    register_user,
    reset_password_with_backup_code,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthUserResponse, responses=COMMON_ERROR_RESPONSES)
def login(payload: LoginRequest) -> AuthUserResponse:
    try:
        user = login_user(payload.username, payload.password)
        return AuthUserResponse(**user)
    except AuthLockoutError as exc:
        raise ApiException(
            status_code=429,
            code="AUTH_RATE_LIMITED",
            message=str(exc),
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="AUTH_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="AUTH_LOGIN_FAILED",
            message="Login failed.",
        )


@router.post("/register", response_model=AuthUserResponse, responses=COMMON_ERROR_RESPONSES)
def register(payload: RegisterRequest) -> AuthUserResponse:
    try:
        user = register_user(payload.username, payload.email, payload.password)
        return AuthUserResponse(**user)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="AUTH_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="AUTH_REGISTRATION_FAILED",
            message="Registration failed.",
        )


@router.post(
    "/reset-password/backup",
    response_model=AuthUserResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def reset_password_backup(payload: ResetPasswordBackupRequest) -> AuthUserResponse:
    try:
        user = reset_password_with_backup_code(
            payload.username,
            payload.backup_code,
            payload.new_password,
        )
        return AuthUserResponse(**user)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="AUTH_VALIDATION_ERROR",
            message=str(exc),
            detail=str(exc),
        )
    except Exception:
        raise ApiException(
            status_code=500,
            code="AUTH_RESET_FAILED",
            message="Backup password reset failed.",
        )
