@echo off
setlocal

cd /d "%~dp0"

echo Running database init script...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0init-databases.ps1"

echo.
echo Done.
pause
