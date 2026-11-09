@echo off
setlocal
cd /d "%~dp0"
title WISP USB-Stick erstellen

echo.
echo  ============================================
echo    WISP auf USB-Stick packen
echo  ============================================
echo.

REM ---- Zielordner erfragen ----------------------------------------------
REM Als Parameter uebergeben (z.B. "WISP USB-Stick erstellen.bat" E:\WISP)
REM oder abfragen.
set "ZIEL=%~1"
if "%ZIEL%"=="" set /p ZIEL="  Zielpfad auf dem USB-Stick (z.B. E:\WISP): "

if "%ZIEL%"=="" (
    echo  Kein Ziel angegeben - Abbruch.
    pause
    exit /b 1
)

if not exist "%ZIEL%\" (
    echo  Ordner "%ZIEL%" existiert nicht - wird erstellt...
    mkdir "%ZIEL%"
    if errorlevel 1 (
        echo  FEHLER: Konnte Ordner nicht erstellen. Ist der Stick eingesteckt?
        pause
        exit /b 1
    )
)

REM ---- Dateien kopieren --------------------------------------------------
echo.
echo  Kopiere WISP nach "%ZIEL%"...

REM Programm-Dateien
for %%f in ("wisp.py" "cloud.py" "ersetzungen.py" "ki.py" "nutzung.py" "postprocess.py" ^
            "platform_support.py" "pill_windows.py" "pill_macos.py" ^
            "requirements.txt" "requirements-gpu.txt" "INSTALLIEREN.bat" ^
            "WISP starten.bat" "WISP Einstellungen.bat" "setup_app.py" "STAND.md" ^
            "README.md" "CLAUDE.md" "AGENTS.md") do (
    copy /y %%f "%ZIEL%\" >nul && echo    + %%f || echo    FEHLER bei %%f
)

REM Asset-Ordner (Icon usw.)
xcopy "assets" "%ZIEL%\assets\" /e /i /y >nul && echo    + assets\
if exist tests xcopy "tests" "%ZIEL%\tests\" /e /i /y >nul && echo    + tests\

echo.
echo  ============================================
echo    Fertig!
echo.
echo    Auf dem anderen PC:
echo      1. Ordner vom Stick auf die Festplatte kopieren ^(nicht direkt vom Stick starten^)
echo      2. Doppelklick auf "INSTALLIEREN.bat"
echo      3. Fragen beantworten - fertig
echo  ============================================
echo.
pause
