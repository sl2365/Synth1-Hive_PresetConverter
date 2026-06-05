
:: =================================================================================
:: Place Synth1 bank folders containing .sy1 presets here: 	input\synth1\
:: Run this batch file, converted files go here: 			output\Converted_Presets\
:: =================================================================================

@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo Running conversion pipeline
echo ==========================================
echo.

set "PYTHON=..\_Tools\python\python.exe"
set "SCRIPT=scripts\convert_s1_hive.py"

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
rem pause
echo Finished successfully. Closing in 3 seconds...
timeout /t 3 /nobreak >nul
exit