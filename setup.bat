@echo off
REM ==============================================================================
REM ASSET HARVESTER - FIRST TIME SETUP
REM ==============================================================================
REM Run this script the first time to install all dependencies.
REM ==============================================================================

echo.
echo ============================================================
echo   Asset Harvester - First Time Setup
echo ============================================================
echo.

REM Check Python version
echo [1/4] Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found!
    echo Please install Python 3.11 or higher from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Install core dependencies
echo.
echo [2/4] Installing core dependencies...
pip install sqlalchemy
if errorlevel 1 (
    echo [ERROR] Failed to install SQLAlchemy!
    pause
    exit /b 1
)
echo [OK] SQLAlchemy installed

REM Install optional GUI dependencies
echo.
echo [3/4] Installing GUI dependencies (optional)...
pip install PyQt6
if errorlevel 1 (
    echo [WARNING] PyQt6 installation failed - GUI will not be available
    echo          You can still use CLI mode: python main.py --cli
) else (
    echo [OK] PyQt6 installed
)

REM Install build dependencies
echo.
echo [4/4] Installing build dependencies (for creating exe)...
pip install pyinstaller
if errorlevel 1 (
    echo [WARNING] PyInstaller installation failed - cannot build exe
) else (
    echo [OK] PyInstaller installed
)

REM Create necessary directories
echo.
echo [INFO] Creating directories...
if not exist "tools" mkdir tools
if not exist "tools\scripts" mkdir tools\scripts

echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Run the application:  run.bat
echo   2. Build as exe:         build.bat
echo.
echo For QuickBMS support (extracting unsupported formats):
echo   - Download from: https://aluigi.altervista.org/quickbms.htm
echo   - Place quickbms.exe in the 'tools' folder
echo.

pause
