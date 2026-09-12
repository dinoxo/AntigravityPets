@echo off
setlocal
cd /d "%~dp0\.."
echo ===================================================
echo   Building Standalone AntigravityPets.exe (Windows)
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller -r desktop_py\requirements.txt

echo Building standalone single-file binary with PyInstaller...
pyinstaller --noconsole --onefile --add-data "assets;assets" --name "AntigravityPets" desktop_py\app.py

if exist "dist\AntigravityPets.exe" (
    echo.
    echo [SUCCESS] Binary created at: dist\AntigravityPets.exe
    echo You can distribute dist\AntigravityPets.exe directly to any Windows PC without requiring Python!
) else (
    echo.
    echo [ERROR] Build failed. Check the output above.
)
pause
