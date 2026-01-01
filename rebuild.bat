@echo off
echo ============================================================
echo   REBUILDING ASSET HARVESTER
echo ============================================================
echo.

cd /d "%~dp0"

echo Finding Python...
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

echo Using Python: %PYTHON%
%PYTHON% --version
echo.

echo Running PyInstaller...
%PYTHON% -m PyInstaller AssetHarvester.spec --noconfirm

echo.
if %ERRORLEVEL% EQU 0 (
    echo ============================================================
    echo   BUILD SUCCESSFUL!
    echo ============================================================
    echo.
    echo EXE location: dist\AssetHarvester\AssetHarvester.exe
    echo.
    echo Run it now? (Y/N)
    set /p RUN=
    if /i "%RUN%"=="Y" (
        start "" "dist\AssetHarvester\AssetHarvester.exe"
    )
) else (
    echo ============================================================
    echo   BUILD FAILED
    echo ============================================================
)

pause
