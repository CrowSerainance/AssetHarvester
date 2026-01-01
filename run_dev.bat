@echo off
echo ============================================================
echo   RUNNING ASSET HARVESTER (Development Mode)
echo ============================================================
echo.

cd /d "F:\2026 PROJECT\AssetHarvester"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PYTHON=py
) else (
    if exist "C:\Python314\python.exe" (
        set PYTHON=C:\Python314\python.exe
    ) else (
        echo [ERROR] Python not found!
        pause
        exit /b 1
    )
)

echo Using: %PYTHON%
%PYTHON% main.py

echo.
echo Application exited with code: %ERRORLEVEL%
pause
