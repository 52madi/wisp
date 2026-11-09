@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\pythonw.exe (
    echo  WISP ist noch nicht installiert. Bitte zuerst INSTALLIEREN.bat ausfuehren.
    pause
    exit /b 1
)
start "" .venv\Scripts\pythonw.exe wisp.py --settings
