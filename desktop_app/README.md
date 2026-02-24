# Desktop App Workspace (`desktop_app`)

This workspace hosts the new stack:
- React + Vite frontend (`frontend/`)
- Tauri desktop shell (`src-tauri/`)
- FastAPI local backend sidecar (`../api_local`)

## Dev bootstrap

1. Start local API:

```powershell
cd ..\api_local
pip install -r requirements.txt
python run_api.py
```

2. Start React frontend:

```powershell
cd ..\desktop_app\frontend
npm install
npm run dev
```

3. Start Tauri shell:

```powershell
cd ..\desktop_app
npm install
npx tauri dev
```

## MSI path (target)

1. Build frontend:

```powershell
cd desktop_app\frontend
npm run build
```

2. Build sidecar exe:

```powershell
pyinstaller --onefile --name lightningbid-api api_local\run_api.py
```

3. Move/copy built sidecar to:

`desktop_app/sidecar/`

4. Build MSI:

```powershell
cd desktop_app
npx tauri build
```

## Notes

- `src-tauri/tauri.conf.json` is already set to bundle MSI and include sidecar.
- `upgradeCode` is fixed for MSI upgrades.
