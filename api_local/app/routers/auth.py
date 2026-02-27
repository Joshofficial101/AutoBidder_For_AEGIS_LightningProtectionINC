from fastapi import APIRouter, Depends

from app.auth_dependencies import AuthenticatedUser, get_bearer_token, get_current_user
from app.errors import ApiException, COMMON_ERROR_RESPONSES
from app.schemas import (
    AuthLogoutResponse,
    AuthUserResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordBackupRequest,
    VerifyPasswordRequest,
    VerifyPasswordResponse,
)
from app.services.auth_service import (
    AuthLockoutError,
    login_user,
    logout_access_token,
    register_user,
    reset_password_with_backup_code,
    verify_user_password,
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


@router.post("/logout", response_model=AuthLogoutResponse, responses=COMMON_ERROR_RESPONSES)
def logout(access_token: str = Depends(get_bearer_token)) -> AuthLogoutResponse:
    try:
        logout_access_token(access_token)
        return AuthLogoutResponse()
    except Exception:
        raise ApiException(
            status_code=500,
            code="AUTH_LOGOUT_FAILED",
            message="Logout failed.",
        )


@router.post(
    "/verify-password",
    response_model=VerifyPasswordResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def verify_password(
    payload: VerifyPasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> VerifyPasswordResponse:
    try:
        is_valid = verify_user_password(current_user.user_id, payload.password)
        return VerifyPasswordResponse(valid=is_valid)
    except Exception:
        raise ApiException(
            status_code=500,
            code="AUTH_VERIFY_PASSWORD_FAILED",
            message="Password verification failed.",
        )
