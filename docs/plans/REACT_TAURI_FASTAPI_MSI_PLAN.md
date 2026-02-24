# React + Tauri + FastAPI(Local) + MSI Migration Plan

## 1) Decision Summary

This direction is viable and practical for your use case:
- React for modern UI.
- Tauri for desktop shell and MSI packaging.
- FastAPI as a local API process (sidecar) so Python logic stays intact.
- Existing Python business logic reused instead of rewritten.

## 2) Research Findings (Official Docs)

1. Tauri supports React and Vite templates, and can also be added to an existing frontend project.
2. Tauri supports bundling external binaries as sidecars using `bundle.externalBin`.
3. Sidecars require explicit capability permissions (`shell:allow-execute` / `shell:allow-spawn`).
4. Tauri Windows packaging supports MSI via WiX Toolset v3, and MSI build is Windows-only.
5. Tauri uses WebView2 on Windows; WebView2 install mode is configurable (`webviewInstallMode`).
6. Tauri MSI updates should keep a stable WiX `upgradeCode`.
7. React docs explicitly deprecate Create React App (CRA) for new apps.
8. Vite supports React templates and is the recommended fast build setup.
9. FastAPI supports standard app bootstrap and local dev (`fastapi dev`), and CORS middleware.
10. Uvicorn supports command-line and programmatic startup (`uvicorn.run`), good for local sidecar server launch.
11. PyInstaller can package Python services into Windows executables (`--onefile`/`--windowed`) for sidecar distribution.

## 3) Target Architecture

- Desktop shell: Tauri app.
- Frontend: React + Vite (TypeScript recommended).
- Backend: FastAPI local server on `127.0.0.1:<port>`.
- Data: SQLite local file (same DB model as now, then evolve if needed).
- Packaging:
  - FastAPI packaged as sidecar executable.
  - Tauri bundles sidecar and builds `.msi`.

## 4) Keep/Move Map (Current Features)

Keep these Python modules as-is initially:
- `src/adapters/excel_loader.py`
- `src/adapters/pdf_loader*.py`
- `src/calculator/bid_calc.py`
- `src/exporters/excel_export.py`
- `src/exporters/pdf_export.py`
- `src/database/*.py`

Move UI behavior out of Flet into React screens:
- File import and parsing progress.
- Bid calculator flow.
- Jobs board + status transitions.
- Calendar view.
- Dashboard metrics.

## 5) Implementation Phases

### Phase A: Stabilize and Freeze Existing Logic (1-2 days)
1. Freeze Python business logic APIs (no functional rewrites).
2. Add a small service boundary layer in Python (functions/classes called by FastAPI routes).
3. Add smoke tests for:
   - Excel load.
   - PDF parse.
   - Bid calculation.
   - Export generation.

Acceptance:
- Existing behavior unchanged from MSI app.

### Phase B: Build FastAPI Local API (3-5 days)
1. Create API package (`api_local/` or `src/api/`) with FastAPI routes:
   - `/health`
   - `/parse/pdf`
   - `/catalog/load`
   - `/bids/preview`
   - `/bids/create`
   - `/jobs/*`
   - `/exports/*`
2. Wrap long-running tasks (PDF parse/export) with background tasks and status polling endpoints.
3. Add CORS config to allow Tauri origin(s) and dev URL.
4. Standardize response and error schemas.

Acceptance:
- All key user actions available via HTTP API with stable JSON contracts.

### Phase C: Build React UI (Professional/Modern) (1-2 weeks)
1. Bootstrap React + Vite + TypeScript.
2. Add app shell layout:
   - Left nav, top bar, module content area.
3. Build screens:
   - Bidding workspace.
   - Jobs board.
   - Calendar.
   - Dashboard.
4. API client layer:
   - typed endpoints, retry, error toasts.
5. State management:
   - lightweight (`zustand` or React Query + local state).

Acceptance:
- Full user flow works in browser mode against local FastAPI.

### Phase D: Integrate Tauri + Sidecar (3-5 days)
1. Create Tauri app around React frontend.
2. Package FastAPI as executable sidecar (PyInstaller).
3. Register sidecar in `tauri.conf.json > bundle.externalBin`.
4. Add capability permissions for sidecar spawn/execute.
5. On app startup:
   - spawn sidecar,
   - wait on `/health`,
   - then load UI.
6. On app shutdown:
   - gracefully stop sidecar.

Acceptance:
- App works offline as a desktop app with no manual Python setup.

### Phase E: MSI Build and Installer Hardening (2-4 days)
1. Configure bundle target as MSI (`targets: "msi"` or list including `msi`).
2. Set a fixed WiX `upgradeCode` (must not change across versions).
3. Decide WebView2 install mode in Tauri config for your distribution needs.
4. Build and test MSI on clean Windows VM.
5. Validate update/repair/uninstall behavior.

Acceptance:
- Uncle can install from MSI and run app without dev tools.

## 6) UI Direction (Professional + Modern)

Recommended stack:
- React + TypeScript + Vite.
- MUI (production-ready component system), with custom theme.

Design spec:
1. Typography:
   - Clear hierarchy (H1/H2/body/caption), consistent spacing scale.
2. Color system:
   - Neutral enterprise base + one accent color.
   - Semantic colors for status (scheduled/in progress/inspection/completed).
3. Layout:
   - Responsive desktop-first shell (minimum 1280 width target, graceful downscale).
4. Components:
   - Dense data tables for bids/jobs.
   - Kanban cards for statuses.
   - Calendar with date filters and quick jump controls.
5. Motion:
   - Minimal transitions for panel changes and async states only.
6. Reliability UX:
   - explicit loading, empty, and error states on every data panel.

## 7) Key Technical Risks and Controls

1. Sidecar startup race condition:
   - Control: health-check gate before rendering app routes.
2. CORS/origin mismatch in desktop webview:
   - Control: explicit allow list and logging of request origin in dev.
3. Heavy PDF parsing blocking UI:
   - Control: background tasks + progress polling + timeout budget.
4. MSI upgrade creating duplicate app:
   - Control: fixed `upgradeCode` and versioning policy.
5. Antivirus false positives with packed binaries:
   - Control: code signing and predictable release artifacts.

## 8) Suggested Execution Order (Exact)

1. Build FastAPI routes around existing Python logic.
2. Add route-level tests and smoke tests.
3. Build React screens against FastAPI in browser mode.
4. Integrate Tauri shell and sidecar lifecycle.
5. Build MSI and validate on clean machine.

## 9) Definition of Done

- All current user-critical functions available in the new stack:
  - PDF parse (text + drawing workflows).
  - Excel catalog import.
  - Bid calculation + preview + save.
  - Job progression and calendar visibility.
  - Export to Excel/PDF.
- App installs from MSI and runs for a non-technical user without setup steps.
- No fullscreen-only button behavior regressions.

## Sources

- Tauri Create Project: https://v2.tauri.app/start/create-project/
- Tauri Vite frontend config (`frontendDist`): https://v2.tauri.app/start/frontend/vite/
- Tauri sidecars (`externalBin`, capabilities, `Command.sidecar`): https://v2.tauri.app/develop/sidecar/
- Tauri Shell plugin: https://v2.tauri.app/plugin/shell/
- Tauri Windows installer (MSI/WiX): https://v2.tauri.app/distribute/windows-installer/
- Tauri config (`targets`, `webviewInstallMode`, `upgradeCode`): https://v2.tauri.app/reference/config/
- Tauri prerequisites (WebView2, VBSCRIPT for MSI): https://v2.tauri.app/start/prerequisites/
- React installation (CRA deprecated): https://react.dev/learn/installation
- Vite getting started (React templates): https://vite.dev/guide/
- FastAPI first steps: https://fastapi.tiangolo.com/tutorial/first-steps/
- FastAPI CORS middleware: https://fastapi.tiangolo.com/tutorial/cors/
- Uvicorn settings (`uvicorn.run`, host/port/workers): https://www.uvicorn.org/settings/
- PyInstaller usage: https://www.pyinstaller.org/en/stable/usage.html
- Material UI overview: https://mui.com/material-ui/getting-started/
- shadcn/ui installation: https://ui.shadcn.com/docs/installation
