@echo off
echo Building ContextSwitcher...

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Build the executable
pyinstaller --onefile --windowed --name="ContextSwitcher" --icon=icon.ico --add-data "gui\\qt\\styles;gui\\qt\\styles" main.py

echo.
echo Build complete! Executable is in dist\ContextSwitcher.exe
echo You can now run the app without terminal by double-clicking the .exe file
pause
