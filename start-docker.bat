@echo off
REM Start Docker Desktop on Windows
REM This script checks if Docker Desktop is running and starts it if needed

echo.
echo Checking Docker status...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Docker Desktop is not running.
    echo Starting Docker Desktop...
    echo.
    
    REM Try to start Docker Desktop
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo Docker Desktop is starting...
        echo Please wait 30-60 seconds for it to fully initialize.
        echo.
        timeout /t 30 /nobreak
    ) else (
        echo ERROR: Docker Desktop not found at default location.
        echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
        pause
        exit /b 1
    )
) else (
    echo Docker is already running!
)

echo.
echo Verifying Docker is responsive...
docker ps >nul 2>&1
if %errorlevel% eq 0 (
    echo ✓ Docker is ready!
    echo.
    echo You can now run:
    echo   docker-compose up -d
    echo.
) else (
    echo Docker is still starting. Please wait a moment and try again.
    echo.
)

pause
