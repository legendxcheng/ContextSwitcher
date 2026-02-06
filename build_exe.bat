@echo off
setlocal

cd /d "%~dp0"

echo Building ContextSwitcher...

set "SPEC=ContextSwitcher.spec"
set "DIST=dist_new"
set "BUILD=build_new"

if not exist "%SPEC%" (
  echo [ERROR] %SPEC% not found in %CD%
  exit /b 1
)

pyinstaller "%SPEC%" --clean --noconfirm --distpath "%DIST%" --workpath "%BUILD%"
if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b 1
)

echo.
echo Build complete: %DIST%\ContextSwitcher.exe
if exist "dist\ContextSwitcher.exe" (
  echo.
  echo To replace dist\ContextSwitcher.exe, close the app and run:
  echo   copy /Y "%DIST%\ContextSwitcher.exe" "dist\ContextSwitcher.exe"
)

exit /b 0
