import math
import os


def _read_float_env(name: str, default: float, min_value: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < min_value:
        return min_value
    return value


def _to_bytes(megabytes: float) -> int:
    return max(1, int(megabytes * 1024 * 1024))


def _to_base64_char_limit(max_bytes: int) -> int:
    return int(math.ceil(max_bytes / 3) * 4)


# Defaults chosen to support real-world plan sets while protecting local memory.
MAX_PDF_MB = _read_float_env("LIGHTNINGBID_MAX_PDF_MB", default=35.0, min_value=1.0)
MAX_EXCEL_MB = _read_float_env("LIGHTNINGBID_MAX_EXCEL_MB", default=15.0, min_value=1.0)

MAX_PDF_BYTES = _to_bytes(MAX_PDF_MB)
MAX_EXCEL_BYTES = _to_bytes(MAX_EXCEL_MB)

# Pydantic max_length limits for base64 string fields.
MAX_PDF_BASE64_CHARS = _to_base64_char_limit(MAX_PDF_BYTES)
MAX_EXCEL_BASE64_CHARS = _to_base64_char_limit(MAX_EXCEL_BYTES)
