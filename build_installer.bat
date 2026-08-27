@echo off
setlocal

cd /d "%~dp0"

set "SPEC=ContextSwitcher.spec"
set "DIST=release\app"
set "BUILD=release\build"
set "INSTALLER_SCRIPT=installer\ContextSwitcher.iss"
set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
  echo [ERROR] Inno Setup 6 was not found.
  echo Install it with: winget install --id JRSoftware.InnoSetup --exact
  exit /b 1
)

echo [1/2] Building ContextSwitcher executable...
python -m PyInstaller "%SPEC%" --clean --noconfirm --distpath "%DIST%" --workpath "%BUILD%"
if errorlevel 1 exit /b 1

echo.
echo [2/2] Building Windows installer...
"%ISCC%" "%INSTALLER_SCRIPT%"
if errorlevel 1 exit /b 1

echo.
echo Build complete: release\installer\ContextSwitcher-Setup-1.2.0.exe

exit /b 0
