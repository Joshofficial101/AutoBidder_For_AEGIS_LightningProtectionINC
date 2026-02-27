import re
import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from src.database.auth_utils import hash_password, verify_password
from src.database.db_connector import DBConnector

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UPPER_PATTERN = re.compile(r"[A-Z]")
LOWER_PATTERN = re.compile(r"[a-z]")
DIGIT_PATTERN = re.compile(r"\d")
SYMBOL_PATTERN = re.compile(r"[^A-Za-z0-9]")

MAX_FAILED_ATTEMPTS = 10
LOCKOUT_MINUTES = 15
SESSION_DURATION_HOURS = 8
SESSION_TOUCH_INTERVAL_SECONDS = 60

COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "letmein",
    "qwerty",
    "qwerty123",
    "12345678",
    "123456789",
    "admin123",
    "welcome1",
}


class AuthLockoutError(ValueError):
    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AuthTokenError(ValueError):
    def __init__(self, message: str, code: str = "AUTH_INVALID_TOKEN") -> None:
        super().__init__(message)
        self.code = code


def _generate_backup_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    chunks = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(chunks)


def _hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_backup_code(value: str) -> str:
    raw = (value or "").strip().upper().replace(" ", "")
    if not raw:
        return ""
    compact = raw.replace("-", "")
    if len(compact) == 16 and compact.isalnum():
        return "-".join(compact[i : i + 4] for i in range(0, 16, 4))
    return raw


def _normalize_username(username: str) -> str:
    value = (username or "").strip()
    if not value:
        raise ValueError("Username is required.")
    if len(value) < 3:
        raise ValueError("Username must be at least 3 characters.")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _create_session_payload(db: DBConnector, user_id: int, username: str) -> Dict[str, Any]:
    now = _utc_now()
    expires_at = now + timedelta(hours=SESSION_DURATION_HOURS)
    access_token = secrets.token_urlsafe(48)
    token_hash = _hash_access_token(access_token)
    now_str = _format_utc(now)
    expires_at_str = _format_utc(expires_at)

    db.purge_stale_auth_sessions(now_str)
    db.create_auth_session(
        user_id=int(user_id),
        token_hash=token_hash,
        created_at=now_str,
        last_used_at=now_str,
        expires_at=expires_at_str,
    )

    return {
        "user_id": int(user_id),
        "username": username,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at_str,
    }


def _validate_password(password: str, username: str | None = None, email: str | None = None) -> str:
    value = password or ""
    if len(value) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if len(value) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    if any(ch.isspace() for ch in value):
        raise ValueError("Password cannot contain spaces.")
    if not UPPER_PATTERN.search(value):
        raise ValueError("Password must include at least one uppercase letter.")
    if not LOWER_PATTERN.search(value):
        raise ValueError("Password must include at least one lowercase letter.")
    if not DIGIT_PATTERN.search(value):
        raise ValueError("Password must include at least one number.")
    if not SYMBOL_PATTERN.search(value):
        raise ValueError("Password must include at least one symbol.")

    lowered = value.lower()
    if lowered in COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common. Choose a stronger password.")
    if username and username.lower() in lowered:
        raise ValueError("Password cannot contain your username.")
    if email:
        email_local = email.split("@", 1)[0].strip().lower()
        if email_local and email_local in lowered:
            raise ValueError("Password cannot contain part of your email.")

    return value


def _validate_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value:
        raise ValueError("Email is required.")
    if not EMAIL_PATTERN.match(value):
        raise ValueError("Email format is invalid.")
    return value


def login_user(username: str, password: str) -> Dict[str, Any]:
    normalized_username = _normalize_username(username)
    if not password:
        raise ValueError("Password is required.")

    db = DBConnector()
    now = _utc_now()
    security_state = db.get_auth_security_by_username(normalized_username)
    if security_state:
        failed_attempts, locked_until_raw, _last_failed_at = security_state
        locked_until = _parse_utc(locked_until_raw)
        if locked_until and locked_until > now:
            seconds_remaining = int((locked_until - now).total_seconds())
            minutes_remaining = max(1, (seconds_remaining + 59) // 60)
            raise AuthLockoutError(
                f"Too many failed login attempts. Try again in {minutes_remaining} minute(s).",
                retry_after_seconds=max(1, seconds_remaining),
            )

    row = db.get_user_by_username(normalized_username)
    is_valid_password = False
    if row:
        _user_id, _stored_username, stored_password_hash = row
        is_valid_password = verify_password(password, stored_password_hash)

    if not row or not is_valid_password:
        failed_attempts = int(security_state[0]) if security_state else 0
        failed_attempts += 1
        locked_until = None
        if failed_attempts >= MAX_FAILED_ATTEMPTS:
            locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)

        db.upsert_auth_security(
            username=normalized_username,
            failed_attempts=failed_attempts,
            locked_until=_format_utc(locked_until) if locked_until else None,
            last_failed_at=_format_utc(now),
            updated_at=_format_utc(now),
        )

        if locked_until:
            raise AuthLockoutError(
                f"Too many failed login attempts. Account locked for {LOCKOUT_MINUTES} minutes.",
                retry_after_seconds=LOCKOUT_MINUTES * 60,
            )
        raise ValueError("Invalid username or password.")

    user_id, stored_username, _stored_password_hash = row
    db.clear_auth_security(normalized_username)
    return _create_session_payload(db, int(user_id), stored_username)


def register_user(username: str, email: str, password: str) -> Dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_email = _validate_email(email)
    normalized_password = _validate_password(
        password,
        username=normalized_username,
        email=normalized_email,
    )

    db = DBConnector()
    password_hash = hash_password(normalized_password)
    backup_code = _generate_backup_code()
    backup_code_hash = hash_password(backup_code)
    user_id = db.create_user(
        normalized_username,
        normalized_email,
        password_hash,
        recovery_code_hash=backup_code_hash,
    )

    if not user_id:
        raise ValueError("Username or email already exists.")

    response = _create_session_payload(db, int(user_id), normalized_username)
    response["backup_code"] = backup_code
    return response


def reset_password_with_backup_code(username: str, backup_code: str, new_password: str) -> Dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_backup_code = _normalize_backup_code(backup_code)
    if not normalized_backup_code:
        raise ValueError("Backup code is required.")

    db = DBConnector()
    row = db.get_user_recovery_by_username(normalized_username)
    if not row:
        raise ValueError("Invalid username or backup code.")

    user_id, stored_username, stored_backup_code_hash = row
    if not stored_backup_code_hash or not verify_password(normalized_backup_code, stored_backup_code_hash):
        raise ValueError("Invalid username or backup code.")

    normalized_password = _validate_password(
        new_password,
        username=normalized_username,
    )

    new_backup_code = _generate_backup_code()
    db.update_user_password_and_recovery(
        user_id=int(user_id),
        password_hash=hash_password(normalized_password),
        recovery_code_hash=hash_password(new_backup_code),
        recovery_code_updated_at=_format_utc(_utc_now()),
    )
    db.clear_auth_security(normalized_username)

    response = _create_session_payload(db, int(user_id), stored_username)
    response["backup_code"] = new_backup_code
    return response


def get_authenticated_user(access_token: str) -> Dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise AuthTokenError("Authentication required.", code="AUTH_MISSING_TOKEN")

    now = _utc_now()
    db = DBConnector()
    session = db.get_auth_session_by_token_hash(_hash_access_token(token))
    if not session:
        raise AuthTokenError("Invalid authentication token.")

    session_id, user_id, username, last_used_at_raw, expires_at_raw, revoked_at_raw = session
    if revoked_at_raw:
        raise AuthTokenError("Authentication token has been revoked.")

    expires_at = _parse_utc(expires_at_raw)
    if not expires_at or expires_at <= now:
        db.revoke_auth_session(int(session_id), _format_utc(now))
        raise AuthTokenError("Session expired. Please sign in again.", code="AUTH_SESSION_EXPIRED")

    last_used_at = _parse_utc(last_used_at_raw)
    if (
        not last_used_at
        or int((now - last_used_at).total_seconds()) >= SESSION_TOUCH_INTERVAL_SECONDS
    ):
        db.touch_auth_session(int(session_id), _format_utc(now))
    return {"user_id": int(user_id), "username": str(username)}


def logout_access_token(access_token: str) -> None:
    token = (access_token or "").strip()
    if not token:
        return

    db = DBConnector()
    session = db.get_auth_session_by_token_hash(_hash_access_token(token))
    if not session:
        return

    session_id = int(session[0])
    db.revoke_auth_session(session_id, _format_utc(_utc_now()))


def verify_user_password(user_id: int, password: str) -> bool:
    if not password:
        return False

    db = DBConnector()
    row = db.get_user_auth_by_id(int(user_id))
    if not row:
        return False

    _resolved_user_id, _username, password_hash = row
    return verify_password(password, password_hash)
