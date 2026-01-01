@echo off
REM ==============================================================================
REM ASSET HARVESTER - QUICK BUILD SCRIPT
REM ==============================================================================
REM Run this to build the executable. Requires Python and PyInstaller.
REM
REM Usage:
REM   build.bat              - Build with console window
REM   build.bat --noconsole  - Build GUI-only (no console)
REM   build.bat --clean      - Clean and rebuild
REM ==============================================================================

echo.
echo ============================================================
echo   Asset Harvester - Build Script
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.11 or higher.
    pause
    exit /b 1
)

REM Check if PyInstaller is available
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller!
        pause
        exit /b 1
    )
)

REM Check if SQLAlchemy is available
python -c "import sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
)

REM Run the build script
echo.
echo [INFO] Starting build...
echo.

python build.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build complete!
echo   Executable: dist\AssetHarvester\AssetHarvester.exe
echo ============================================================
echo.

pause
