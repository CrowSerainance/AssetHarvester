@echo off
REM ==============================================================================
REM DEBUG LAUNCHER - Shows errors before closing
REM ==============================================================================
cd /d "%~dp0"
echo.
echo ============================================================
echo   Asset Harvester - Debug Mode
echo ============================================================
echo.
echo Working directory: %CD%
echo.

if exist "dist\AssetHarvester\AssetHarvester.exe" (
    echo Running from dist\AssetHarvester\...
    cd dist\AssetHarvester
    AssetHarvester.exe --check
    echo.
    echo ------------------------------------------------------------
    echo Now running full app...
    echo ------------------------------------------------------------
    AssetHarvester.exe
) else (
    echo [ERROR] Executable not found!
    echo Expected: dist\AssetHarvester\AssetHarvester.exe
    echo.
    echo Did you run build.bat first?
)

echo.
echo ============================================================
echo   Application exited. Press any key to close.
echo ============================================================
pause
