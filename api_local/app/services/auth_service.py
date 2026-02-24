import re
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


def _generate_backup_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    chunks = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(chunks)


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

    return {
        "user_id": int(user_id),
        "username": stored_username,
    }


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

    return {
        "user_id": int(user_id),
        "username": normalized_username,
        "backup_code": backup_code,
    }


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

    return {
        "user_id": int(user_id),
        "username": stored_username,
        "backup_code": new_backup_code,
    }
