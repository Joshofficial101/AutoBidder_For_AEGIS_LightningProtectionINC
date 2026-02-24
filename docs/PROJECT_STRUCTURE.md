# Project Structure

## Active Application Paths

- `desktop_app/`
  - `frontend/` React + Vite UI
  - `src-tauri/` Tauri desktop shell
  - `sidecar/` bundled FastAPI executable for desktop packaging
- `api_local/` FastAPI app (dev/runtime API layer)
- `src/` shared domain logic (parsing, calculation, export, models)

## Supporting Paths

- `docs/` product and technical docs
- `docs/plans/` planning and migration documents
- `tests/` test and validation scripts
- `tools/` operational scripts
- `data/` input/output/reference data
- `assets/` static project assets

## Root Scripts

- `setup.cmd` install Python dependencies for backend logic/API
- `run_desktop.cmd` run Tauri desktop app in dev mode
- `run_frontend_safe.cmd` frontend build/preview utility
