@echo off
REM --- Windows Launch Script for 
Bid ---

echo Activating Virtual Environment...
call .venv\Scripts\activate.bat

if exist .venv\Scripts\python.exe (
    echo Launching LightningBid GUI...
    REM Run the application as a module using the venv's Python executable
    .venv\Scripts\python.exe -m src.gui.run_gui
) else (
    echo ERROR: Virtual environment not found. Please run setup.cmd first.
)

REM Deactivate the environment after the application closes
call .venv\Scripts\deactivate.bat