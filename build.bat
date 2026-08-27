@echo off
setlocal

cd /d "%~dp0"

set "DIST=release\app"
set "BUILD=release\build"

echo Building ContextSwitcher...

REM Use a pinned PyInstaller version for reproducible Qt bundles
python -m pip install pyinstaller==6.17.0

REM Use the same executable output consumed by the installer build.
python -m PyInstaller ContextSwitcher.spec --clean --noconfirm --distpath "%DIST%" --workpath "%BUILD%"
if errorlevel 1 exit /b 1

echo.
echo Build complete! Executable is in release\app\ContextSwitcher.exe
echo You can now run the app without terminal by double-clicking the .exe file
pause
