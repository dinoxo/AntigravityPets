@echo off
setlocal
cd /d "%~dp0"
echo ===================================================
echo   Starting Antigravity Pets (Windows Companion)
echo ===================================================

:: Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
python -m pip install -q -r desktop_py\requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Could not verify/install requirements. Attempting to start anyway...
)

:: Launch Companion
echo Launching desktop overlay...
python desktop_py\app.py
if %errorlevel% neq 0 (
    echo [ERROR] Companion closed with an error.
    pause
)
