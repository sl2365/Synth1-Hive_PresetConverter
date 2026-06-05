
:: =================================================================================
:: This turns the "scripts\convert_s1_hive.py" script into an EXE
:: Run this batch file, built EXE will be in the "DIST" folder
:: =================================================================================

@echo off
setlocal

cd /d "%~dp0"

set "PYTHON=..\_Tools\python\python.exe"
set "SCRIPT=%CD%\scripts\convert_s1_hive.py"
set "DIST=%CD%"
set "WORK=%CD%\build"
set "SPEC=%CD%\build"

if not exist "%PYTHON%" (
    echo ERROR: Python not found:
    echo %PYTHON%
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERROR: Script not found:
    echo %SCRIPT%
    echo.
    pause
    exit /b 1
)

"%PYTHON%" -m PyInstaller --onefile --name "Synth1-Hive Preset Converter" --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" "%SCRIPT%"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
rem pause
echo Finished successfully. Closing in 3 seconds...
timeout /t 3 /nobreak >nul
exit