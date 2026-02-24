from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db_connector import DBConnector


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_db() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        with sqlite3.connect(str(DBConnector.DB_PATH), timeout=2) as conn:
            row = conn.execute("SELECT 1;").fetchone()
        ok = bool(row and row[0] == 1)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok" if ok else "fail",
            "required": True,
            "message": "SQLite connection healthy." if ok else "SQLite query returned unexpected result.",
            "duration_ms": duration_ms,
            "metadata": {"db_path": str(DBConnector.DB_PATH)},
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "fail",
            "required": True,
            "message": f"SQLite check failed: {exc}",
            "duration_ms": duration_ms,
            "metadata": {"db_path": str(DBConnector.DB_PATH)},
        }


def _check_sidecar() -> Dict[str, Any]:
    sidecar_required = os.getenv("LIGHTNINGBID_REQUIRE_SIDECAR", "0").lower() in {"1", "true", "yes"}
    configured_path = os.getenv("LIGHTNINGBID_SIDECAR_PATH")
    default_path = ROOT / "desktop_app" / "sidecar" / "lightningbid-api.exe"
    sidecar_path = Path(configured_path) if configured_path else default_path

    exists = sidecar_path.exists()
    if exists:
        return {
            "status": "ok",
            "required": sidecar_required,
            "message": "Sidecar binary found.",
            "duration_ms": 0.0,
            "metadata": {"path": str(sidecar_path)},
        }
    if sidecar_required:
        return {
            "status": "fail",
            "required": True,
            "message": "Sidecar binary is required but missing.",
            "duration_ms": 0.0,
            "metadata": {"path": str(sidecar_path)},
        }
    return {
        "status": "degraded",
        "required": False,
        "message": "Sidecar binary not found (not required in this runtime mode).",
        "duration_ms": 0.0,
        "metadata": {"path": str(sidecar_path)},
    }


def build_readiness_report(started_at: datetime, app_version: str) -> Dict[str, Any]:
    api_uptime = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
    checks = {
        "api": {
            "status": "ok",
            "required": True,
            "message": "API process is running.",
            "duration_ms": 0.0,
            "metadata": {
                "version": app_version,
                "uptime_seconds": round(api_uptime, 2),
            },
        },
        "db": _check_db(),
        "sidecar": _check_sidecar(),
    }

    overall = "ok"
    for check in checks.values():
        if check["status"] == "fail" and check["required"]:
            overall = "fail"
            break
    if overall != "fail" and any(check["status"] == "degraded" for check in checks.values()):
        overall = "degraded"

    return {
        "status": overall,
        "ready": overall != "fail",
        "timestamp": _utc_now(),
        "checks": checks,
    }
