from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

from app.correlation import get_correlation_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", get_correlation_id()),
        }

        for attr in (
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "error_code",
        ):
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _build_log_dir() -> Path:
    configured = os.getenv("LIGHTNINGBID_LOG_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "logs"


def _has_handler(root_logger: logging.Logger, handler_type: str) -> bool:
    for handler in root_logger.handlers:
        if getattr(handler, "_lightningbid_handler_type", None) == handler_type:
            return True
    return False


def configure_structured_logging() -> None:
    level_name = os.getenv("LIGHTNINGBID_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = JsonFormatter()

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
    root_logger.setLevel(level)

    enable_file_logs = os.getenv("LIGHTNINGBID_ENABLE_FILE_LOGS", "1").lower() in {"1", "true", "yes"}
    if enable_file_logs:
        log_dir = _build_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        max_bytes = _read_int_env("LIGHTNINGBID_LOG_MAX_BYTES", 5 * 1024 * 1024)
        backup_count = _read_int_env("LIGHTNINGBID_LOG_BACKUP_COUNT", 14)

        main_log_file = os.getenv("LIGHTNINGBID_LOG_FILE", "lightningbid-api.jsonl")
        main_log_path = log_dir / main_log_file
        if not _has_handler(root_logger, "central_log"):
            main_file_handler = RotatingFileHandler(
                filename=str(main_log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            main_file_handler.setLevel(level)
            main_file_handler.setFormatter(formatter)
            setattr(main_file_handler, "_lightningbid_handler_type", "central_log")
            root_logger.addHandler(main_file_handler)

        enable_alert_log = os.getenv("LIGHTNINGBID_ENABLE_ALERT_LOG", "1").lower() in {"1", "true", "yes"}
        if enable_alert_log and not _has_handler(root_logger, "critical_alert_log"):
            alert_level_name = os.getenv("LIGHTNINGBID_ALERT_LEVEL", "ERROR").upper()
            alert_level = getattr(logging, alert_level_name, logging.ERROR)
            alert_log_file = os.getenv("LIGHTNINGBID_ALERT_FILE", "critical-alerts.jsonl")
            alert_log_path = log_dir / alert_log_file
            alert_handler = RotatingFileHandler(
                filename=str(alert_log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            alert_handler.setLevel(alert_level)
            alert_handler.setFormatter(formatter)
            setattr(alert_handler, "_lightningbid_handler_type", "critical_alert_log")
            root_logger.addHandler(alert_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setFormatter(formatter)
