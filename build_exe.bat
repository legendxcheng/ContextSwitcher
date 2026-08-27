@echo off
setlocal

cd /d "%~dp0"

echo Building ContextSwitcher...

set "SPEC=ContextSwitcher.spec"
set "DIST=dist"
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

exit /b 0
