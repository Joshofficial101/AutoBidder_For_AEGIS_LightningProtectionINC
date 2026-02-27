from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import ApiException
from app.services.auth_service import AuthTokenError, get_authenticated_user

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: int
    username: str


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not credentials:
        raise ApiException(
            status_code=401,
            code="AUTH_MISSING_TOKEN",
            message="Authentication required.",
            detail="Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer":
        raise ApiException(
            status_code=401,
            code="AUTH_INVALID_SCHEME",
            message="Authentication required.",
            detail="Authorization scheme must be Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = (credentials.credentials or "").strip()
    if not token:
        raise ApiException(
            status_code=401,
            code="AUTH_MISSING_TOKEN",
            message="Authentication required.",
            detail="Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_current_user(token: str = Depends(get_bearer_token)) -> AuthenticatedUser:
    try:
        payload = get_authenticated_user(token)
    except AuthTokenError as exc:
        raise ApiException(
            status_code=401,
            code=exc.code,
            message=str(exc),
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        user_id=int(payload["user_id"]),
        username=str(payload["username"]),
    )
