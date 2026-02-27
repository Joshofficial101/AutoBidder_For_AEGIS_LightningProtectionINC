from pathlib import Path

from app.settings import MAX_EXCEL_BYTES, MAX_EXCEL_MB, MAX_PDF_BYTES, MAX_PDF_MB


class PayloadTooLargeError(ValueError):
    pass


def estimate_base64_decoded_size(raw_base64: str) -> int:
    raw = (raw_base64 or "").strip()
    if not raw:
        return 0
    padding = 0
    if raw.endswith("=="):
        padding = 2
    elif raw.endswith("="):
        padding = 1
    return max(0, (len(raw) * 3) // 4 - padding)


def _assert_size_within_limit(actual_size: int, max_size: int, label: str, max_mb: float) -> None:
    if actual_size <= max_size:
        return
    actual_mb = actual_size / (1024 * 1024)
    raise PayloadTooLargeError(
        f"{label} is too large ({actual_mb:.2f} MB). Max allowed is {max_mb:.2f} MB."
    )


def assert_excel_file_within_limit(path: Path) -> None:
    _assert_size_within_limit(path.stat().st_size, MAX_EXCEL_BYTES, "Excel file", MAX_EXCEL_MB)


def assert_pdf_file_within_limit(path: Path) -> None:
    _assert_size_within_limit(path.stat().st_size, MAX_PDF_BYTES, "PDF file", MAX_PDF_MB)


def assert_excel_base64_within_limit(raw_base64: str) -> None:
    decoded_size = estimate_base64_decoded_size(raw_base64)
    _assert_size_within_limit(decoded_size, MAX_EXCEL_BYTES, "Excel payload", MAX_EXCEL_MB)


def assert_pdf_base64_within_limit(raw_base64: str) -> None:
    decoded_size = estimate_base64_decoded_size(raw_base64)
    _assert_size_within_limit(decoded_size, MAX_PDF_BYTES, "PDF payload", MAX_PDF_MB)
