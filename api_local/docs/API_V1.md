# LightningBid API v1

Base URL: `http://127.0.0.1:8765`

- Swagger UI: `/api/v1/docs`
- OpenAPI JSON: `/api/v1/openapi.json`

## Contract Rules

- All request bodies are schema-validated.
- Unknown request fields are rejected.
- Dates must use `YYYY-MM-DD`.
- Validation and business-rule failures return structured `ApiError`.
- Every response includes `X-Correlation-ID` for request tracing.

## Jobs Workflow Rules

State machine:

`awaiting_approval -> scheduled -> in_progress -> inspection -> completed -> invoiced`

Required fields per transition:

- `awaiting_approval -> scheduled` (via `POST /api/v1/jobs/{job_id}/approve`):
  - `scheduled_date`, `assigned_crew`, `note`
- `scheduled -> in_progress`:
  - `start_date`, `assigned_crew` (if not already assigned), `note`
- `in_progress -> inspection`:
  - `note`
- `inspection -> completed`:
  - `completion_date`, `note`
- `completed -> invoiced`:
  - `invoice_number`, `invoice_date`, `note`

## Reliability Endpoints

- `GET /health`: basic liveness
- `GET /health/live`: explicit liveness
- `GET /health/ready`: readiness for startup dependencies (`api`, `db`, `sidecar`)

`/health/ready` returns `503` when a required dependency fails.

## Standard Error Response

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "One or more fields are invalid.",
  "errors": [
    {
      "type": "date_from_datetime_parsing",
      "loc": ["query", "start_date"],
      "msg": "Input should be a valid date"
    }
  ]
}
```

## Example: Bid Preview (Path Input)

### Request

`POST /api/v1/bids/preview`

```json
{
  "pricing_file_path": "C:/Pricing/ERICO Installer 6.1.25 Price List.xlsx",
  "pricing_sheet": "Sheet1",
  "compliance_code": "DUAL",
  "project_data": {
    "project_name": "AEGIS Distribution Center",
    "building_height_ft": 35,
    "roof_area_sqft": 5000,
    "perimeter_ft": 284
  },
  "workers": [
    {
      "name": "Lead Installer",
      "wage_per_hour": 42.5,
      "hours": 18
    }
  ]
}
```

## Example: Readiness Check

### Request

`GET /health/ready`

### Response (200)

```json
{
  "status": "ok",
  "ready": true,
  "timestamp": "2026-02-20T11:30:00Z",
  "checks": {
    "api": {
      "status": "ok",
      "required": true,
      "message": "API process is running.",
      "duration_ms": 0.0,
      "metadata": {
        "version": "1.0.0",
        "uptime_seconds": 12.5
      }
    },
    "db": {
      "status": "ok",
      "required": true,
      "message": "SQLite connection healthy.",
      "duration_ms": 0.8,
      "metadata": {
        "db_path": "C:/.../src/database/app.db"
      }
    },
    "sidecar": {
      "status": "degraded",
      "required": false,
      "message": "Sidecar binary not found (not required in this runtime mode).",
      "duration_ms": 0.0,
      "metadata": {
        "path": "C:/.../desktop_app/sidecar/lightningbid-api.exe"
      }
    }
  }
}
```

### Response (200)

```json
{
  "project_name": "AEGIS Distribution Center",
  "subtotal": 11400.75,
  "total_with_markup": 14050.92,
  "final_bid_amount": 14050.92,
  "material_total": 9200.2,
  "labor_total": 2200.55,
  "sections": [
    {
      "name": "Air Terminals",
      "items": 9,
      "material_total": 1540.0,
      "labor_total": 0.0,
      "section_total": 1540.0
    }
  ]
}
```

## Example: Parse PDF (Base64 Input)

### Request

`POST /api/v1/parse/pdf/base64`

```json
{
  "file_name": "electrical-plans.pdf",
  "file_bytes_base64": "<base64-encoded-pdf>"
}
```

### Response (200)

```json
{
  "extracted": {
    "project_info": {
      "project_name": "BC23-001053"
    },
    "building_dimensions": {
      "height": 35.0,
      "area": 5000.0,
      "perimeter": 284.0
    }
  }
}
```

## Example: Approve Job

### Request

`POST /api/v1/jobs/52/approve`

```json
{
  "user_id": 3,
  "scheduled_date": "2026-02-25",
  "note": "Approved after customer sign-off"
}
```

### Response (200)

```json
{
  "user_id": 3,
  "job": {
    "job_id": 52,
    "project_name": "Warehouse Retrofit",
    "status": "scheduled",
    "status_display": "Scheduled",
    "bid_amount": 18650.0,
    "scheduled_date": "2026-02-25",
    "completion_date": null
  }
}
```
