@echo off
setlocal
REM --- Safe frontend launcher (build + static preview) ---

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%"

if not exist "desktop_app\frontend\package.json" (
    echo ERROR: Could not find desktop_app\frontend\package.json
    echo Run this script from the project root folder.
    goto :fail
)

REM Clear restrictive env vars that can break npm/python in some shells
set "NPM_CONFIG_OFFLINE="
set "PIP_NO_INDEX="
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "GIT_HTTP_PROXY="
set "GIT_HTTPS_PROXY="

REM Ensure Node is available in this process
if exist "C:\Program Files\nodejs\npm.cmd" set "PATH=C:\Program Files\nodejs;%PATH%"

REM Modes:
REM   default       -> build + serve
REM   --build-only  -> build only, then exit
REM   --serve-only  -> skip build, serve existing dist
set "MODE=%~1"
set "SKIP_BUILD=0"
set "SKIP_SERVE=0"
if /I "%MODE%"=="--build-only" set "SKIP_SERVE=1"
if /I "%MODE%"=="--serve-only" set "SKIP_BUILD=1"

pushd "desktop_app\frontend"

if "%SKIP_BUILD%"=="0" (
    echo [1/2] Building frontend...
    call cmd /c npm run build
    if errorlevel 1 (
        echo.
        echo Build failed.
        goto :frontend_fail
    )
) else (
    echo [1/2] Skipping build in serve-only mode.
)

if "%SKIP_SERVE%"=="1" (
    echo.
    echo Build completed.
    goto :success
)

if not exist "dist\index.html" (
    echo ERROR: dist\index.html not found.
    echo Run without --serve-only first to build the frontend.
    goto :frontend_fail
)

echo [2/2] Starting static preview server...
echo Open http://127.0.0.1:4173 in your browser.
echo Press Ctrl+C to stop.
call cmd /c npm run preview:static
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
    echo.
    echo Static preview exited with error code %APP_EXIT%.
    goto :frontend_fail
)

goto :success

:frontend_fail
popd
goto :fail

:success
popd
popd
endlocal
exit /b 0

:fail
popd
endlocal
exit /b 1
