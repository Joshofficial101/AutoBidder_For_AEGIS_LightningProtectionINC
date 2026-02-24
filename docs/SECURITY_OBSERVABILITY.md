# Security + Observability (Offline/Desktop)

This project now includes:

1. Reusable dependency scan command (Python + Node)
2. Central structured API logs (JSONL)
3. Critical error alert logs (JSONL, `ERROR`+ by default)

## Dependency Scan Command

Run from project root:

```powershell
tools\security_scan.cmd
```

Why two files:
- `tools\security_scan.ps1` contains the actual scan logic.
- `tools\security_scan.cmd` is a wrapper so you can run the scan easily from Command Prompt or by double-clicking.

Optional safe npm auto-fix pass:

```powershell
tools\security_scan.cmd -Fix
```

Optional Python audit timeout override (seconds):

```powershell
tools\security_scan.cmd -PythonTimeoutSeconds 240
```

What it does:

- Python scans:
  - local `.venv` installed package set (`pip-audit -l`)
- Node scans:
  - `desktop_app`
  - `desktop_app/frontend`
- Writes timestamped outputs to `reports/security/<timestamp>/`
- Writes `summary.json` with totals and command status
- Clears proxy env vars during scan to avoid stale local proxy values
- Uses a command timeout for Python scan to avoid indefinite runs

Exit codes:

- `0`: scan completed, no vulnerabilities detected
- `2`: command/runtime error during scan
- `3`: vulnerabilities detected

## Central Logs + Critical Alerts

By default, API startup writes JSON logs to:

- `logs/lightningbid-api.jsonl` (all log levels)
- `logs/critical-alerts.jsonl` (`ERROR` and above)

Both files rotate automatically by size.

## Logging Environment Variables

- `LIGHTNINGBID_LOG_LEVEL` (default: `INFO`)
- `LIGHTNINGBID_LOG_DIR` (default: `<repo>/logs`)
- `LIGHTNINGBID_LOG_FILE` (default: `lightningbid-api.jsonl`)
- `LIGHTNINGBID_ALERT_FILE` (default: `critical-alerts.jsonl`)
- `LIGHTNINGBID_ALERT_LEVEL` (default: `ERROR`)
- `LIGHTNINGBID_LOG_MAX_BYTES` (default: `5242880`)
- `LIGHTNINGBID_LOG_BACKUP_COUNT` (default: `14`)
- `LIGHTNINGBID_ENABLE_FILE_LOGS` (default: `1`)
- `LIGHTNINGBID_ENABLE_ALERT_LOG` (default: `1`)
