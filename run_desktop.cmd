@echo off
setlocal
REM --- Windows Launch Script for LightningBid Desktop (Tauri + FastAPI sidecar) ---

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%"

if not exist "desktop_app\package.json" (
    echo ERROR: Could not find desktop_app\package.json
    echo Run this script from the project root folder.
    goto :fail
)

REM Clear restrictive env vars that can break npm/cargo in some shells
set "NPM_CONFIG_OFFLINE="
set "PIP_NO_INDEX="
set "CARGO_NET_OFFLINE="
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "GIT_HTTP_PROXY="
set "GIT_HTTPS_PROXY="
set "LIGHTNINGBID_LOG_DIR=%ROOT_DIR%logs"

REM Ensure Node and Cargo are available in this process
if exist "C:\Program Files\nodejs\npx.cmd" set "PATH=C:\Program Files\nodejs;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\cargo.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

REM Load Visual Studio C++ build environment (needed by Rust/MSVC)
set "VCVARS_BAT="
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set "VCVARS_BAT=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)
if "%VCVARS_BAT%"=="" if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set "VCVARS_BAT=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)
if "%VCVARS_BAT%"=="" (
    echo ERROR: Could not find vcvars64.bat for Visual Studio Build Tools.
    echo Install VS 2022 Build Tools with C++ workload and Windows SDK.
    goto :fail
)

echo Loading Visual Studio build environment...
call "%VCVARS_BAT%" >nul 2>&1

where link >nul 2>&1
if errorlevel 1 (
    echo ERROR: link.exe not found after loading VS environment.
    goto :fail
)

REM Stop any stale local API process already listening on port 8765.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8765 .*LISTENING"') do (
    if not "%%P"=="0" (
        echo Stopping existing process on port 8765 - PID %%P...
        taskkill /PID %%P /F >nul 2>&1
    )
)

pushd "desktop_app"
echo Launching LightningBid Desktop...
npx tauri dev
set "APP_EXIT=%ERRORLEVEL%"
popd

if not "%APP_EXIT%"=="0" (
    echo.
    echo Desktop app exited with error code %APP_EXIT%.
    goto :fail
)

popd
endlocal
exit /b 0

:fail
popd
endlocal
exit /b 1
