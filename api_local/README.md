# Local FastAPI Backend (`api_local`)

This service powers the active React+Tauri desktop app and reuses shared Python logic in `src/`.

## Run (dev)

```powershell
cd api_local
pip install -r requirements.txt
python run_api.py
```

Server:
- `http://127.0.0.1:8765`
- Versioned Swagger: `http://127.0.0.1:8765/api/v1/docs`
- Versioned OpenAPI JSON: `http://127.0.0.1:8765/api/v1/openapi.json`

## Endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/bids/preview`
- `POST /api/v1/bids/preview/base64`
- `POST /api/v1/parse/pdf`
- `POST /api/v1/parse/pdf/base64`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/jobs/board`
- `PATCH /api/v1/jobs/{job_id}/status`
- `POST /api/v1/jobs/{job_id}/approve`
- `GET /api/v1/calendar/jobs`
- `GET /api/v1/calendar/day`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/reset-password/backup`

## Error Contract

All non-2xx responses now use this schema:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "One or more fields are invalid.",
  "errors": []
}
```

See `api_local/docs/API_V1.md` for request/response examples.

## Notes

- Designed to become the Tauri sidecar process.
- Keeps current parser/calculator behavior by importing from `src/`.
- Runs DB maintenance at startup (daily backup + pending migrations).
- Adds structured JSON logs with per-request correlation IDs (`X-Correlation-ID`).
- Writes central log stream to `logs/lightningbid-api.jsonl` and critical alerts to `logs/critical-alerts.jsonl`.
