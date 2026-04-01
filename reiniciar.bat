@echo off
cd /d "%~dp0"
echo Reconstruyendo backend sin cache...
docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache backend
if errorlevel 1 exit /b 1
echo Recreando backend, nginx y celery...
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate backend nginx celery_worker celery_beat
if errorlevel 1 exit /b 1
echo.
echo Listo. En el navegador: Ctrl+Shift+R (recarga forzada).
pause
