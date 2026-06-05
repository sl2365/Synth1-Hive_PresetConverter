@echo off
setlocal

:: Set path to AutoHotkey64.exe:
set "AHK_EXE=..\..\AutoHotkey64.exe"
set "SCRIPT=%~dp0synth1_resave_bank.ahk"

if not exist "%AHK_EXE%" (
    echo ERROR: AutoHotkey executable not found:
    echo %AHK_EXE%
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

echo Running Synth1 resave script...
echo.
start "" "%AHK_EXE%" "%SCRIPT%"

echo Script launched.
echo You can close this window.
echo.
rem pause
echo Finished. Closing in 2 seconds...
timeout /t 2 /nobreak >nul
exit
