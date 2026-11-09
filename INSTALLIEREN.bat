@echo off
setlocal
cd /d "%~dp0"
title WISP Installation

set "AUTO=0"
if /i "%~1"=="--auto" set "AUTO=1"

echo.
echo  ============================================
echo    WISP Installation (Push-to-Talk Diktat)
echo  ============================================
echo.

REM ---- 1. Python pruefen / finden --------------------------------------
set "PY="
where python >nul 2>&1 && set "PY=python"

if not defined PY (
    echo  FEHLER: Python wurde auf diesem PC nicht gefunden.
    echo.
    echo  Bitte zuerst installieren:
    echo    https://www.python.org/downloads/
    echo.
    echo  WICHTIG im Installer:
    echo    [X] "Add python.exe to PATH" anhaken!
    echo.
    echo  Nach der Installation dieses Fenster neu starten.
    if "%AUTO%"=="0" pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Gefunden: %%v

REM ---- 2. Virtuelle Umgebung anlegen -----------------------------------
if not exist .venv (
    echo.
    echo  Erstelle Python-Umgebung ^(einmalig, ca. 30 Sekunden^)...
    python -m venv .venv
    if errorlevel 1 (
        echo  FEHLER: Umgebung konnte nicht erstellt werden.
        if "%AUTO%"=="0" pause
        exit /b 1
    )
)

REM ---- 3. Abhaengigkeiten installieren ---------------------------------
echo.
echo  Installiere Abhaengigkeiten ^(ca. 2-5 Minuten je nach Internet^)...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if errorlevel 1 goto :fehler

.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 goto :fehler

REM ---- 4. GPU? ----------------------------------------------------------
if "%AUTO%"=="1" (
    goto :keine_gpu
)
echo.
choice /c JN /n /m "  Hat dieser PC eine NVIDIA-GPU? [J=ja N=nein] "
if errorlevel 2 goto :keine_gpu

echo  Lade CUDA-Unterstuetzung ^(~1 GB, dauert laenger^)...
.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt --quiet
if errorlevel 1 (
    echo  Warnung: CUDA-Pakete schlugen fehl - WISP laeuft trotzdem auf CPU.
)
:keine_gpu

REM ---- 5. Teststart -----------------------------------------------------
echo.
echo  Kurzer Funktionstest...
.venv\Scripts\python.exe -c "import faster_whisper; import sounddevice; import PIL; print('alles ok')" 
if errorlevel 1 goto :fehler

REM ---- 6. Verknuepfungen -----------------------------------------------
if "%AUTO%"=="1" (
    .venv\Scripts\python.exe setup_app.py
    goto :fertig
)
choice /c JN /n /m "  Desktop- und Startmenue-Verknuepfungen anlegen? [J=ja N=nein] "
if not errorlevel 2 .venv\Scripts\python.exe setup_app.py
echo.
choice /c JN /n /m "  WISP automatisch bei Windows-Start? [J=ja N=nein] "
if not errorlevel 2 .venv\Scripts\python.exe setup_app.py --autostart

:fertig
echo.
echo  ============================================
echo    Installation fertig!
echo.
echo    Starten:   Doppelklick auf "WISP starten.bat"
echo    Einstell.: "WISP Einstellungen.bat" oder Tray-Symbol
echo  ============================================
echo.
if "%AUTO%"=="0" pause
exit /b 0

:fehler
echo.
echo  FEHLER bei der Installation. Internetverbindung pruefen und erneut versuchen.
echo  Log siehe oben.
if "%AUTO%"=="0" pause
exit /b 1
