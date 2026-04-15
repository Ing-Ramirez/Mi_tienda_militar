@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0..\.."

pushd "%REPO_ROOT%" || (
    echo [ERROR] No se pudo abrir la carpeta del script.
    if not defined NO_PAUSE pause
    exit /b 1
)

set "PROJECT_NAME=mi_tienda_militar"
set "COMPOSE=docker compose -p %PROJECT_NAME% -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev"
set "BUILD_SERVICES=backend celery_worker celery_beat"
set "UP_SERVICES=backend nginx celery_worker celery_beat"
set "MODE=%~1"
set "BUILD_ARGS=--pull"
set "SCRIPT_DIR=%~dp0"
set "MAIN_ROOT=..\..\.."
set "MAIN_ENV=..\..\..\.env.dev"
set "IS_WORKTREE="

where docker >nul 2>&1 || goto :docker_missing
call docker compose version >nul 2>&1 || goto :compose_missing
call docker info >nul 2>&1 || goto :docker_not_running

if /I not "%SCRIPT_DIR%"=="%SCRIPT_DIR:.claude\worktrees=%" set "IS_WORKTREE=1"
if defined IS_WORKTREE (
    if exist "%MAIN_ENV%" (
        fc /b ".env.dev" "%MAIN_ENV%" >nul 2>&1
        if errorlevel 1 goto :worktree_env_mismatch
    )
)

if /I "%MODE%"=="nocache" (
    set "BUILD_ARGS=--pull --no-cache"
) else if not "%MODE%"=="" (
    goto :usage
)

echo.
echo [ADVERTENCIA] Limpieza profunda para casos especiales.
echo Este script va a:
echo   1. Bajar el stack del proyecto y borrar contenedores, imagenes y volumenes.
echo   2. Limpiar cache de build y basura Docker sin uso.
echo   3. Reconstruir y levantar el proyecto desde cero.
echo.
echo Se perderan los datos locales de PostgreSQL y Redis de este proyecto.
echo Usa este BAT solo cuando Docker este muy sucio o el entorno local este roto.
echo.

if defined DRY_RUN goto :dry_run

if not defined NO_CONFIRM (
    choice /C SN /N /M "Continuar con la limpieza profunda? [S/N]: "
    if errorlevel 2 goto :cancelled
)

echo Bajando y eliminando recursos del proyecto...
call %COMPOSE% down --remove-orphans --volumes --rmi all
if errorlevel 1 goto :compose_error

echo Limpiando cache de build...
call docker builder prune -af
if errorlevel 1 goto :docker_cleanup_error

echo Limpiando recursos Docker sin uso...
call docker system prune -af --volumes
if errorlevel 1 goto :docker_cleanup_error

echo Reconstruyendo imagenes desde cero...
call %COMPOSE% build %BUILD_ARGS% %BUILD_SERVICES%
if errorlevel 1 goto :compose_error

echo Levantando servicios...
call %COMPOSE% up -d --force-recreate --no-build %UP_SERVICES%
if errorlevel 1 goto :compose_error

echo.
echo Listo. Entorno recreado desde cero.
call :offer_superuser
if errorlevel 1 goto :superuser_error
echo En el navegador: Ctrl+Shift+R para recarga forzada.
goto :success

:dry_run
echo [DRY RUN] Validaciones completadas.
echo [DRY RUN] Se ejecutaria: compose down --remove-orphans --volumes --rmi all
echo [DRY RUN] Se ejecutaria: docker builder prune -af
echo [DRY RUN] Se ejecutaria: docker system prune -af --volumes
echo [DRY RUN] Se ejecutaria: compose build %BUILD_ARGS% %BUILD_SERVICES%
echo [DRY RUN] Se ejecutaria: compose up -d --force-recreate --no-build %UP_SERVICES%
echo [DRY RUN] Al final ofrecera crear un superusuario de Django.
goto :success

:offer_superuser
if defined SKIP_SUPERUSER (
    echo Creacion de superusuario omitida por SKIP_SUPERUSER=1.
    exit /b 0
)

if defined NO_PAUSE if not defined CREATE_SUPERUSER if not defined SUPERUSER_EMAIL (
    echo Creacion interactiva de superusuario omitida por NO_PAUSE=1.
    exit /b 0
)

if not defined CREATE_SUPERUSER (
    echo.
    choice /C SN /N /M "Deseas crear un superusuario de Django al finalizar? [S/N]: "
    if errorlevel 2 (
        echo Creacion de superusuario omitida.
        exit /b 0
    )
)

echo.
echo Se solicitaran correo y contrasena del superusuario.
echo Si el correo ya existe, se actualizara ese usuario y se promocionara a superusuario.
call powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_superuser.ps1" -ProjectName "%PROJECT_NAME%" -ComposeFile1 "docker-compose.yml" -ComposeFile2 "docker-compose.dev.yml"
exit /b %errorlevel%

:usage
echo Uso:
echo   %~nx0
echo   %~nx0 nocache
echo.
echo Sin parametros: limpieza profunda + rebuild con cache.
echo nocache: limpieza profunda + rebuild sin cache.
goto :fail

:docker_missing
echo [ERROR] Docker no esta instalado o no esta en PATH.
goto :fail

:compose_missing
echo [ERROR] El comando "docker compose" no esta disponible.
goto :fail

:docker_not_running
echo [ERROR] Docker Desktop o el daemon de Docker no esta corriendo.
goto :fail

:worktree_env_mismatch
echo [ERROR] Este worktree tiene un .env.dev distinto al del repo principal.
echo [ERROR] Reiniciar asi puede romper backend y DB por credenciales diferentes.
echo [ERROR] Sincroniza ".env.dev" con "%MAIN_ENV%" o ejecuta desde "%MAIN_ROOT%".
goto :fail

:docker_cleanup_error
echo.
echo [ERROR] La limpieza global de Docker fallo. Revisa los mensajes anteriores.
goto :fail

:compose_error
echo.
echo [ERROR] La recreacion desde cero fallo. Revisa los mensajes anteriores.
goto :fail

:superuser_error
echo.
echo [ERROR] El entorno quedo recreado, pero la creacion del superusuario fallo.
goto :fail

:cancelled
echo Operacion cancelada por el usuario.
goto :success

:success
popd
if not defined NO_PAUSE pause
exit /b 0

:fail
popd
if not defined NO_PAUSE pause
exit /b 1
