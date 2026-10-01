@echo off
rem PyQt Study Helper - one-time setup: installs packages and makes a desktop shortcut.
cd /d "%~dp0"

rem "python --version" also catches the Microsoft Store stub that exists when Python isn't installed
python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo [!] Python was not found.
    echo     Install Python 3.10+ from https://www.python.org/downloads/
    echo     and check "Add python.exe to PATH" during setup. Then run install.bat again.
    echo.
    pause
    exit /b 1
)

echo [1/4] Installing required packages...
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo [!] Package install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo [2/4] Installing Qt Designer (optional)...
python -m pip install --upgrade PyQt5Designer >nul 2>nul
if errorlevel 1 echo     Qt Designer package could not be installed - you can still use your own Designer.

echo [3/4] Installing the built-in browser for web AI (optional, about 70 MB)...
python -m pip install --upgrade PyQtWebEngine >nul 2>nul
if errorlevel 1 echo     Built-in browser could not be installed - web AI will open in your normal browser.

echo [4/4] Creating desktop shortcut...
python tools\make_shortcut.py

echo.
echo Done! Double-click the desktop icon to start.
pause
