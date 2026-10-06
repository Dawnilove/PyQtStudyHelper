@echo off
rem PyQt Study Helper - one-time setup: installs packages and makes a desktop shortcut.
cd /d "%~dp0"

rem ---- find Python: "python" first, then the "py" launcher ------------------------------
rem ("python --version" also catches the Microsoft Store stub that exists when Python isn't installed)
set "PY=python"
python --version >nul 2>nul
if errorlevel 1 (
    set "PY=py -3"
    py -3 --version >nul 2>nul
    if errorlevel 1 goto :nopython
)

rem ---- needs Python 3.10 or newer --------------------------------------------------------
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo.
    echo [!] Your Python is too old:
    %PY% --version
    echo     PyQt Study Helper needs Python 3.10 or newer.
    echo     Install a new Python from https://www.python.org/downloads/
    echo     ^(check "Add python.exe to PATH"^), then run install.bat again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% --version') do echo Using %%v

echo.
echo [1/4] Installing required packages...
%PY% -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo.
    echo     Trying again for this Windows user only ^(no admin rights needed^)...
    %PY% -m pip install --user --upgrade -r requirements.txt
    if errorlevel 1 goto :pipfailed
)

echo.
echo [2/4] Installing Qt Designer (optional)...
%PY% -m pip install --upgrade PyQt5Designer >nul 2>nul
if errorlevel 1 echo     Qt Designer package could not be installed - you can still use your own Designer.

echo.
echo [3/4] Checking that everything works...
%PY% -c "import PyQt5.QtWidgets, keyring; print('    OK: PyQt5', __import__('PyQt5.QtCore', fromlist=['x']).PYQT_VERSION_STR)"
if errorlevel 1 goto :pipfailed

echo.
echo [4/4] Creating desktop shortcut...
%PY% tools\make_shortcut.py
if errorlevel 1 echo     Could not create the shortcut. Start with the launcher .bat file in this folder instead.

echo.
echo Done! Double-click the new PyQt study helper icon on the desktop to start.
pause
exit /b 0

:nopython
echo.
echo [!] Python was not found.
echo     1. Install Python 3.10+ from https://www.python.org/downloads/
echo     2. On the first setup screen, check "Add python.exe to PATH".
echo     3. Close this window and run install.bat again.
echo.
pause
exit /b 1

:pipfailed
echo.
echo [!] The packages could not be installed.
echo     - Check the internet connection (school/company networks sometimes block pip).
echo     - Close other programs that use Python and try again.
echo     - Still stuck? Copy the red text above and ask for help.
echo.
pause
exit /b 1
