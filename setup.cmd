@echo off
setlocal
REM --- Windows Setup Script for LightningBid (Python backend deps) ---

echo Checking for Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Python not found. Please install Python 3.9 or newer and ensure it is in your PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python Virtual Environment...
    python -m venv .venv
) else (
    echo Virtual environment already exists.
)

echo Activating Virtual Environment...
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing core dependencies from requirements.txt...
pip install -r requirements.txt

if exist "api_local\requirements.txt" (
    echo Installing API dependencies from api_local\requirements.txt...
    pip install -r api_local\requirements.txt
)

echo.
echo ====================================
echo SETUP COMPLETE!
echo Start the desktop app with: run_desktop.cmd
echo (Requires Node.js and Rust toolchain for Tauri development.)
echo ====================================

REM Deactivate the environment after setup
call .venv\Scripts\deactivate.bat

pause
endlocal
