# Installation Guide - LightningBid

## Common Installation Issues

### Issue: "pip is not recognized"

**Problem:** You're trying to use `pip` but Python isn't in your PATH, or you're not using the virtual environment.

**Solution:** Always use the virtual environment's Python!

---

## ✅ Correct Way to Install Packages

### Step 1: Navigate to Project Directory
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
```

### Step 2: Use Virtual Environment's Python
```powershell
# Install package
.venv\Scripts\python.exe -m pip install flet

# Or install all requirements
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## ✅ Correct Way to Run the GUI

### Option 1: Using Python Module
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe -m src.gui.run_gui
```

### Option 2: Direct Python Script
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe src\gui\run_gui.py
```

---

## Quick Reference Commands

### Install Flet
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe -m pip install flet
```

### Install All Requirements
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Run GUI
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe -m src.gui.run_gui
```

### Run Command Line Version
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe -m src.main
```

### Run Tests
```powershell
cd C:\Users\Skyhi\PycharmProjects\PythonProject
.venv\Scripts\python.exe test_system.py
```

---

## Why Use `.venv\Scripts\python.exe`?

Your project has a **virtual environment** (`.venv` folder) that contains:
- Isolated Python installation
- All your project dependencies
- Separate from system Python

**Always use the virtual environment's Python** to ensure you're using the right packages!

---

## Troubleshooting

### "pip is not recognized"
✅ **Use:** `.venv\Scripts\python.exe -m pip install flet`  
❌ **Don't use:** `pip install flet`

### "python is not recognized"
✅ **Use:** `.venv\Scripts\python.exe`  
❌ **Don't use:** `python`

### "Module not found"
- Make sure you're in the project directory
- Make sure you're using the virtual environment's Python
- Install the package: `.venv\Scripts\python.exe -m pip install <package>`

---

## Creating a Shortcut Script (Optional)

Create a file `run_gui.bat` in your project root:

```batch
@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m src.gui.run_gui
pause
```

Then double-click `run_gui.bat` to run the GUI!

---

## Summary

**Always remember:**
1. Navigate to project directory first
2. Use `.venv\Scripts\python.exe` (not just `python` or `pip`)
3. Use `-m pip` instead of just `pip`

This ensures you're using the correct Python environment with all your packages!

