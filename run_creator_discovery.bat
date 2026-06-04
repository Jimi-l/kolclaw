@echo off
setlocal EnableExtensions

rem Run from the folder where this .bat file lives, even if PowerShell is in another directory.
cd /d "%~dp0"

rem Usage examples:
rem   .\run_creator_discovery.bat 2
rem   .\run_creator_discovery.bat 60
rem   .\run_creator_discovery.bat 120
rem Or set MINUTES first:
rem   $env:MINUTES=60; .\run_creator_discovery.bat

if not "%~1"=="" (
    set "MINUTES=%~1"
)

if "%MINUTES%"=="" (
    set /p "MINUTES=How many minutes should creator discovery run? "
)

echo(%MINUTES%| findstr /r "^[1-9][0-9]*$" >nul
if errorlevel 1 (
    echo.
    echo ERROR: Minutes must be a positive whole number, for example 2, 60, or 120.
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo.
        echo ERROR: Could not find python or py on PATH. Please install Python 3.11+ or add it to PATH.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py -3.11"
) else (
    set "PYTHON_CMD=python"
)

echo.
echo Running creator discovery for %MINUTES% minute(s)...
echo Command:
echo   %PYTHON_CMD% -m search_agent creator-discovery --browser-channel chrome --max-candidates 999999 --max-minutes %MINUTES% --max-records 999999 --log-level INFO
echo.

%PYTHON_CMD% -m search_agent creator-discovery --browser-channel chrome --max-candidates 999999 --max-minutes %MINUTES% --max-records 999999 --log-level INFO
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Creator discovery exited with code %EXIT_CODE%.
) else (
    echo Creator discovery finished successfully.
)
echo.
pause
exit /b %EXIT_CODE%
