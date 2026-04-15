@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0..\.."

pushd "%REPO_ROOT%" || (
    echo [ERROR] No se pudo abrir la carpeta del proyecto.
    if not defined NO_PAUSE pause
    exit /b 1
)

set "PROJECT_NAME=mi_tienda_militar"
set "COMPOSE=docker compose -p %PROJECT_NAME% -f docker-compose.yml -f docker-compose.dev.yml"
set "APP_LABEL=%~1"
set "VERBOSITY=%~2"
set "SCRIPT_DIR=%~dp0"
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

call %COMPOSE% ps --services --filter "status=running" 2>nul | findstr /I "backend" >nul 2>&1
if errorlevel 1 goto :backend_not_running

if not defined VERBOSITY set "VERBOSITY=2"

if defined DRY_RUN goto :dry_run

if "%APP_LABEL%"=="" (
    echo Ejecutando todos los tests del proyecto...
    echo.
    call %COMPOSE% exec -T backend python manage.py test --verbosity=%VERBOSITY%
) else (
    echo Ejecutando tests de: %APP_LABEL%
    echo.
    call %COMPOSE% exec -T backend python manage.py test %APP_LABEL% --verbosity=%VERBOSITY%
)

if errorlevel 1 goto :tests_failed
goto :success

:dry_run
if "%APP_LABEL%"=="" (
    echo [DRY RUN] Se ejecutaria: manage.py test --verbosity=%VERBOSITY%
) else (
    echo [DRY RUN] Se ejecutaria: manage.py test %APP_LABEL% --verbosity=%VERBOSITY%
)
goto :success

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
echo [ERROR] Sincroniza ".env.dev" con "%MAIN_ENV%" o ejecuta desde el repo principal.
goto :fail

:backend_not_running
echo [ERROR] El contenedor backend no esta corriendo.
echo Levanta el stack primero con: actualizar.bat
goto :fail

:tests_failed
echo.
echo [FAIL] Uno o mas tests fallaron. Revisa los mensajes anteriores.
goto :fail

:success
popd
if not defined NO_PAUSE pause
exit /b 0

:fail
popd
if not defined NO_PAUSE pause
exit /b 1
