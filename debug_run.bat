@echo off
echo ============================================================
echo   Asset Harvester - Debug Launcher
echo ============================================================
echo.

cd /d "F:\2026 PROJECT\AssetHarvester\dist\AssetHarvester"
echo Current directory: %CD%
echo.

echo Checking if exe exists...
if exist "AssetHarvester.exe" (
    echo [OK] AssetHarvester.exe found
) else (
    echo [ERROR] AssetHarvester.exe NOT FOUND!
    echo.
    echo Did you build the project? Run build.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Running dependency check...
echo ============================================================
AssetHarvester.exe --check

echo.
echo ============================================================
echo   Running path check...
echo ============================================================
AssetHarvester.exe --paths

echo.
echo ============================================================
echo   Starting application...
echo ============================================================
AssetHarvester.exe

echo.
echo ============================================================
echo   Application exited with code: %ERRORLEVEL%
echo ============================================================
pause
