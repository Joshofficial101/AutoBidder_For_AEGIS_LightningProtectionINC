# Sidecar Placeholder

Place the packaged FastAPI executable here.
Expected name in Tauri config: `lightningbid-api` (platform suffix is handled at bundle time).

Planned build command:

```powershell
pyinstaller --onefile --name lightningbid-api api_local\run_api.py
```
