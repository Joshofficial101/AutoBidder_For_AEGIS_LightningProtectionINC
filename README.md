# LightningBid

React + Tauri desktop application with a local FastAPI backend for lightning protection bid workflows.

## Current Stack

- Desktop shell: `desktop_app/src-tauri` (Tauri)
- Frontend UI: `desktop_app/frontend` (React + Vite + TypeScript)
- Local backend API: `api_local` (FastAPI)
- Shared business logic: `src` (calculators, parsers, exporters, models)

## Project Layout

- `api_local/` API routers, schemas, and services
- `desktop_app/` desktop shell, sidecar wiring, frontend
- `src/` core domain logic reused by API services
- `docs/` architecture and feature docs
- `tests/` utility and integration test scripts
- `tools/` operational scripts (security scan, etc.)

## Setup (Windows)

1. Install Python 3.9+, Node.js, and Rust toolchain (for Tauri).
2. Run:

```cmd
setup.cmd
```

## Launch Desktop App

```cmd
run_desktop.cmd
```

## Frontend-Only Build/Preview

```cmd
run_frontend_safe.cmd
```

## Notes

- Legacy Flet UI files were removed; React+Tauri is the active UI path.
- Structure reference: `docs/PROJECT_STRUCTURE.md`
- API documentation: `api_local/docs/API_V1.md`
- Security/observability: `docs/SECURITY_OBSERVABILITY.md`
