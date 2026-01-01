@echo off
REM ==============================================================================
REM ASSET HARVESTER - QUICK LAUNCH SCRIPT
REM ==============================================================================
REM Run this to start Asset Harvester without building an exe.
REM Useful for development and testing.
REM ==============================================================================

echo.
echo ============================================================
echo   Asset Harvester - Starting...
echo ============================================================
echo.

REM Check dependencies first
python -c "import sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

REM Run the application
python main.py %*

pause
