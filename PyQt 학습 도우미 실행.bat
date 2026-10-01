@echo off
rem PyQt Study Helper - double-click to run. You can also drop a .py / .ui file onto this file.
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw run.py %*
) else (
    start "" python run.py %*
)
