@echo off
REM --- Windows Setup Script for LightningBid ---

echo Checking for Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Python not found. Please install Python 3.9 or newer and ensure it is in your PATH.
    pause
    exit /b 1
)

echo Creating Python Virtual Environment...
python -m venv .venv

echo Activating Virtual Environment...
call .venv\Scripts\activate.bat

echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

REM Grant execution permission to the run script (not needed for .cmd, but good practice for .ps1 if used)
REM We will just rely on calling the run script directly.

echo.
echo ====================================
echo SETUP COMPLETE!
echo Run the application next time with: run_gui.cmd
echo ====================================

REM Deactivate the environment after setup
call .venv\Scripts\deactivate.bat

pause