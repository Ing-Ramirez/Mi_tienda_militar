@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0..\.."

pushd "%REPO_ROOT%" || (
    echo [ERROR] No se pudo abrir la carpeta del script.
    if not defined NO_PAUSE pause
    exit /b 1
)

set "PROJECT_NAME=mi_tienda_militar"
set "COMPOSE=docker compose -p %PROJECT_NAME% -f docker-compose.yml -f docker-compose.dev.yml"
set "BUILD_SERVICES=backend celery_worker celery_beat"
set "UP_SERVICES=backend nginx celery_worker celery_beat"
set "MODE=%~1"
set "BUILD_ARGS="
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
        if exist ".env.dev" (
            fc /b ".env.dev" "%MAIN_ENV%" >nul 2>&1
            if errorlevel 1 goto :worktree_env_mismatch
        )
    )
)

if /I "%MODE%"=="build" (
    set "BUILD_ARGS="
) else if /I "%MODE%"=="nocache" (
    set "BUILD_ARGS=--no-cache"
) else if not "%MODE%"=="" (
    goto :usage
)

if defined DRY_RUN goto :dry_run

if /I "%MODE%"=="build" goto :rebuild
if /I "%MODE%"=="nocache" goto :rebuild

echo Aplicando cambios normales del proyecto...
echo Recreando servicios sin limpiar imagenes ni volumenes...
echo Usa "%~nx0 build" si cambiaste requirements.txt o Dockerfile.
call %COMPOSE% up -d --force-recreate --no-build %UP_SERVICES%
if errorlevel 1 goto :compose_error

echo.
echo Listo. Cambios aplicados sin limpieza profunda.
echo En el navegador: Ctrl+Shift+R para recarga forzada.
goto :success

:rebuild
echo Aplicando cambios del proyecto con reconstruccion de imagenes...
if /I "%MODE%"=="nocache" (
    echo Modo: rebuild sin cache.
) else (
    echo Modo: rebuild con cache.
)
call %COMPOSE% build %BUILD_ARGS% %BUILD_SERVICES%
if errorlevel 1 goto :compose_error

call %COMPOSE% up -d --force-recreate --no-build %UP_SERVICES%
if errorlevel 1 goto :compose_error

echo.
echo Listo. Cambios aplicados con reconstruccion de imagenes.
echo En el navegador: Ctrl+Shift+R para recarga forzada.
goto :success

:dry_run
if /I "%MODE%"=="build" (
    echo [DRY RUN] Se ejecutaria: compose build %BUILD_SERVICES%
    echo [DRY RUN] Se ejecutaria: compose up -d --force-recreate --no-build %UP_SERVICES%
) else if /I "%MODE%"=="nocache" (
    echo [DRY RUN] Se ejecutaria: compose build --no-cache %BUILD_SERVICES%
    echo [DRY RUN] Se ejecutaria: compose up -d --force-recreate --no-build %UP_SERVICES%
) else (
    echo [DRY RUN] Se ejecutaria: compose up -d --force-recreate --no-build %UP_SERVICES%
)
goto :success

:usage
echo Uso:
echo   %~nx0
echo   %~nx0 build
echo   %~nx0 nocache
echo.
echo Sin parametros: aplica cambios normales sin limpiar Docker.
echo build: reconstruye imagenes con cache.
echo nocache: reconstruye imagenes sin cache.
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
echo [ERROR] Actualizar asi puede romper backend y DB por credenciales diferentes.
echo [ERROR] Sincroniza ".env.dev" con "%MAIN_ENV%" o ejecuta desde "%MAIN_ROOT%".
goto :fail

:compose_error
echo.
echo [ERROR] La actualizacion del proyecto fallo. Revisa los mensajes anteriores.
goto :fail

:success
popd
if not defined NO_PAUSE pause
exit /b 0

:fail
popd
if not defined NO_PAUSE pause
exit /b 1
