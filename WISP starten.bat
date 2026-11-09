@echo off
setlocal
cd /d "%~dp0"

REM Installation fertig? -> normal starten
if exist .venv\Scripts\pythonw.exe goto :starten

REM Noch nicht installiert -> Installer anbieten
echo.
echo  WISP ist auf diesem PC noch nicht installiert.
echo.
choice /c JN /n /m "  Jetzt installieren? Danach startet WISP automatisch. [J=auch N=nein] "
if errorlevel 2 exit /b 1

call INSTALLIEREN.bat

:starten
if not exist .venv\Scripts\pythonw.exe (
    echo  FEHLER: Installation unvollstaendig. Bitte INSTALLIEREN.bat ausfuehren.
    pause
    exit /b 1
)
start "" .venv\Scripts\pythonw.exe wisp.py
