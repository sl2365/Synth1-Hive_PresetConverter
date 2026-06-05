
:: =================================================================================
:: Place INIT.h2p preset here: 						ROOT\
:: Run this batch file, Hive-Report.ini goes here: 	ROOT\
:: =================================================================================

@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo Running conversion pipeline
echo ==========================================
echo.

set "PYTHON=..\_Tools\python\python.exe"
set "SCRIPT=scripts\preset_parser_diff_values.py"

if not exist "%PYTHON%" (
    echo ERROR: Python not found.
    echo %CD%\%PYTHON%
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERROR: Script not found.
    echo %CD%\%SCRIPT%
    echo.
    pause
    exit /b 1
)

"%PYTHON%" "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo ERROR: Script failed.
    pause
    exit /b 1
)

echo.
echo Finished successfully. Closing in 3 seconds...
timeout /t 3 /nobreak >nul
exit