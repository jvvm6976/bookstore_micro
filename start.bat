@echo off
REM Bookstore Microservices - Quick Startup Script for Windows

setlocal enabledelayedexpansion

cls
echo.
echo ==============================================================
echo   BOOKSTORE MICROSERVICES - STARTUP SCRIPT
echo ==============================================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [OK] Docker found: 
docker --version
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running
    echo Please start Docker Desktop and try again
    pause
    exit /b 1
)

echo [OK] Docker is running
echo.

REM Get directory
set SCRIPT_DIR=%~dp0
cd /d !SCRIPT_DIR!

echo [INFO] Working directory: !SCRIPT_DIR!
echo.

REM Menu
echo Choose an option:
echo.
echo 1. Clean & Start (removes old containers, fresh build)
echo 2. Start (quick start with existing images)
echo 3. Stop (stop all services)
echo 4. Restart (restart all services)
echo 5. View Logs (follow logs from all services)
echo 6. Test System (run quick connectivity test)
echo 7. Database MySQL (connect to MySQL)
echo 8. Database PostgreSQL (connect to PostgreSQL)
echo 9. Remove All (delete all containers and local data)
echo.

set /p choice="Enter choice (1-9): "

if "%choice%"=="1" goto clean_start
if "%choice%"=="2" goto quick_start
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto restart
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto test
if "%choice%"=="7" goto mysql
if "%choice%"=="8" goto postgres
if "%choice%"=="9" goto remove_all

echo [ERROR] Invalid choice
goto end

:clean_start
echo.
echo [1/3] Removing old containers...
docker compose down -v
echo [OK] Old containers removed
echo.
echo [2/3] Building images (this may take 3-5 minutes)...
docker compose build --no-cache
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo [OK] Images built successfully
echo.
echo [3/3] Starting services...
docker compose up -d
echo [OK] Services started
echo.
echo Waiting for services to initialize (30 seconds)...
timeout /t 30 /nobreak
echo.
echo [SUCCESS] System is ready!
echo.
echo Next steps:
echo 1. Check status: docker compose ps
echo 2. View logs: docker compose logs -f
echo 3. Test API: curl http://localhost:8000/api/proxy/books/
echo 4. Read QUICK_START.md for more information
echo.
goto end

:quick_start
echo.
echo [1/1] Starting services...
docker compose up -d
echo [OK] Services started
echo.
echo Waiting for services to initialize (20 seconds)...
timeout /t 20 /nobreak
echo.
echo Check status: docker compose ps
goto end

:stop
echo.
echo Stopping all services...
docker compose stop
echo [OK] All services stopped
goto end

:restart
echo.
echo Restarting all services...
docker compose restart
echo [OK] All services restarted
echo.
echo Waiting for services (10 seconds)...
timeout /t 10 /nobreak
goto end

:logs
echo.
echo [INFO] Showing live logs (Ctrl+C to stop)
echo.
docker compose logs -f
goto end

:test
echo.
echo Testing system connectivity...
echo.

REM Test API Gateway
echo Testing API Gateway (port 8000)...
curl -s http://localhost:8000/api/proxy/books/ >nul 2>&1
if errorlevel 1 (
    echo [FAILED] API Gateway not responding
) else (
    echo [OK] API Gateway is responding
)

REM Test Customer Service
echo Testing Customer Service (port 8001)...
curl -s http://localhost:8001/api/customers/ >nul 2>&1
if errorlevel 1 (
    echo [FAILED] Customer Service not responding
) else (
    echo [OK] Customer Service is responding
)

REM Test Book Service
echo Testing Book Service (port 8002)...
curl -s http://localhost:8002/api/books/ >nul 2>&1
if errorlevel 1 (
    echo [FAILED] Book Service not responding
) else (
    echo [OK] Book Service is responding
)

REM Test Cart Service
echo Testing Cart Service (port 8003)...
curl -s http://localhost:8003/api/carts/ >nul 2>&1
if errorlevel 1 (
    echo [FAILED] Cart Service not responding
) else (
    echo [OK] Cart Service is responding
)

echo.
echo [INFO] Test complete. More details:
echo - Full status: docker compose ps
echo - Service logs: docker compose logs service-name
goto end

:mysql
echo.
echo Connecting to MySQL...
echo Host: localhost
echo Port: 3307
echo User: root
echo Password: root
echo Database: bookstore_db
echo.
echo Choose connection method:
echo 1. MySQL Command Line
echo 2. Show connection info only
echo.
set /p mysql_choice="Enter choice (1-2): "

if "%mysql_choice%"=="1" (
    mysql -h localhost -P 3307 -u root -p
) else (
    echo MySQL Connection Details:
    echo Host: localhost
    echo Port: 3307
    echo User: root
    echo Password: root
    echo.
    echo Use DBeaver or MySQL Workbench for GUI access
)
goto end

:postgres
echo.
echo Connecting to PostgreSQL...
echo Host: localhost
echo Port: 5432
echo User: postgres
echo Password: root
echo Database: bookstore_db
echo.
echo Note: psql must be installed to use command line
echo Use DBeaver or pgAdmin for GUI access
goto end

:remove_all
echo.
echo [WARNING] This will delete all containers and local data!
set /p confirm="Type 'yes' to confirm: "

if /i "%confirm%"=="yes" (
    echo.
    echo Removing all containers and volumes...
    docker compose down -v
    echo [OK] All removed
) else (
    echo [CANCELLED] Nothing was removed
)
goto end

:end
echo.
pause
