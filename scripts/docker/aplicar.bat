@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ============================================================================
::  aplicar.bat  —  Franja Pixelada
::  Aplica cualquier cambio de codigo al stack Docker en ejecucion.
::
::  Detecta automaticamente que cambio y toma la accion minima necesaria.
::
::  CUANDO FUNCIONA (aplica sin rebuild):
::    - Archivos Python (.py): vistas, modelos, serializers, tasks, signals...
::    - Templates HTML (index.html)
::    - Archivos de configuracion Django dentro de backend/
::    - Archivos de Celery
::
::  CUANDO NECESITA REBUILD (imagenes Docker):
::    - requirements.txt  → nueva libreria instalada
::    - Dockerfile        → cambia la imagen base
::    - entrypoint.sh     → cambia el script de arranque
::
::  CUANDO NECESITA RECREAR (contenedores desde cero):
::    - docker-compose.yml o docker-compose.dev.yml
::    - .env.dev (variables de entorno)
::
::  CUANDO ADEMAS CORRE MIGRACIONES:
::    - Nuevos archivos en cualquier migrations/
::
::  CUANDO NECESITAS RECARGAR EL NAVEGADOR:
::    - templates HTML y archivos estaticos (siempre, automaticamente)
::
::  NO FUNCIONA SI:
::    - Agregaste un paquete a requirements.txt pero no usas la opcion 'build'
::    - Creaste un nuevo modelo sin correr makemigrations primero
::    - Cambiaste .env.dev sin recrear contenedores
::    - El stack no esta levantado (usa actualizar.bat primero)
::
::  USO:
::    aplicar.bat              → deteccion automatica por git
::    aplicar.bat codigo       → fuerza restart de backend y Celery
::    aplicar.bat build        → rebuild de imagen + restart
::    aplicar.bat migraciones  → solo corre las migraciones pendientes
::    aplicar.bat nginx        → recarga config de Nginx
::    aplicar.bat todo         → rebuild + recrear + migrate (equivale a actualizar.bat build)
:: ============================================================================

set "REPO_ROOT=%~dp0..\.."

pushd "%REPO_ROOT%" || (
    echo [ERROR] No se pudo abrir la carpeta del proyecto.
    if not defined NO_PAUSE pause
    exit /b 1
)

set "PROJECT_NAME=mi_tienda_militar"
set "COMPOSE=docker compose -p %PROJECT_NAME% -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev"
set "BACKEND_SERVICES=backend celery_worker celery_beat"
set "MODE=%~1"
set "SCRIPT_DIR=%~dp0"
set "MAIN_ENV=..\..\..\.env.dev"
set "IS_WORKTREE="
set "CHANGES_FILE=%TEMP%\fp_aplicar_changes.txt"

:: Flags de accion (0=no, 1=si)
set "FLAG_REBUILD=0"
set "FLAG_RECREATE=0"
set "FLAG_RESTART=0"
set "FLAG_MIGRATE=0"
set "FLAG_NGINX=0"

:: ── Validaciones previas ─────────────────────────────────────────────────────
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

:: ── Modo manual (argumento explicito) ────────────────────────────────────────
if /I "%MODE%"=="codigo"      ( set "FLAG_RESTART=1"  && goto :mostrar_plan )
if /I "%MODE%"=="py"          ( set "FLAG_RESTART=1"  && goto :mostrar_plan )
if /I "%MODE%"=="build"       ( set "FLAG_REBUILD=1"  && goto :mostrar_plan )
if /I "%MODE%"=="rebuild"     ( set "FLAG_REBUILD=1"  && goto :mostrar_plan )
if /I "%MODE%"=="migraciones" ( set "FLAG_MIGRATE=1"  && goto :mostrar_plan )
if /I "%MODE%"=="migrate"     ( set "FLAG_MIGRATE=1"  && goto :mostrar_plan )
if /I "%MODE%"=="nginx"       ( set "FLAG_NGINX=1"    && goto :mostrar_plan )
if /I "%MODE%"=="todo"        ( set "FLAG_REBUILD=1" && set "FLAG_MIGRATE=1" && goto :mostrar_plan )
if not "%MODE%"==""           ( goto :usage )

:: ── Deteccion automatica de cambios via git ──────────────────────────────────
echo Detectando archivos modificados...

where git >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Git no encontrado. Asumiendo cambio de codigo general.
    set "FLAG_RESTART=1"
    goto :mostrar_plan
)

:: Recopilar todos los cambios: unstaged + staged + nuevos sin seguimiento
if exist "%CHANGES_FILE%" del "%CHANGES_FILE%"
git diff --name-only           2>nul >> "%CHANGES_FILE%"
git diff --cached --name-only  2>nul >> "%CHANGES_FILE%"
git ls-files --others --exclude-standard 2>nul >> "%CHANGES_FILE%"

if not exist "%CHANGES_FILE%" (
    echo [AVISO] No se pudo leer estado de git. Aplicando restart de codigo.
    set "FLAG_RESTART=1"
    goto :mostrar_plan
)

for /f %%A in ("%CHANGES_FILE%") do if %%~zA==0 (
    echo No se detectaron cambios en git.
    echo Si hiciste cambios sin "git add", usa: aplicar.bat codigo
    goto :sin_cambios
)

:: Evaluar cada tipo de archivo
findstr /I "requirements.txt" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_REBUILD=1" && echo   [rebuild] requirements.txt modificado )

findstr /I "Dockerfile" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_REBUILD=1" && echo   [rebuild] Dockerfile modificado )

findstr /I "entrypoint.sh" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_REBUILD=1" && echo   [rebuild] entrypoint.sh modificado )

findstr /I "docker-compose" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_RECREATE=1" && echo   [recrear] docker-compose modificado )

findstr /I "\.env" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_RECREATE=1" && echo   [recrear] .env modificado )

findstr /I "nginx" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_NGINX=1" && echo   [nginx] configuracion de Nginx modificada )

findstr /I "migrations" "%CHANGES_FILE%" >nul 2>&1
if not errorlevel 1 ( set "FLAG_MIGRATE=1" && echo   [migraciones] nuevas migraciones detectadas )

:: Si no cayo en ninguna categoria especial → restart de codigo
if "%FLAG_REBUILD%"=="0" if "%FLAG_RECREATE%"=="0" (
    set "FLAG_RESTART=1"
    echo   [codigo] cambios de Python / templates detectados
)

:: Rebuild implica restart
if "%FLAG_REBUILD%"=="1" set "FLAG_RESTART=0"
if "%FLAG_RECREATE%"=="1" set "FLAG_RESTART=0"

goto :mostrar_plan

:: ── Plan de ejecucion ────────────────────────────────────────────────────────
:mostrar_plan
echo.
echo ┌─────────────────────────────────────────────┐
echo │         Plan de accion detectado            │
echo ├─────────────────────────────────────────────┤
if "%FLAG_REBUILD%"=="1"  echo │  [1] Rebuild de imagen Docker               │
if "%FLAG_RECREATE%"=="1" echo │  [1] Recrear contenedores                   │
if "%FLAG_RESTART%"=="1"  echo │  [1] Restart de backend + Celery            │
if "%FLAG_MIGRATE%"=="1"  echo │  [2] Ejecutar migraciones Django            │
if "%FLAG_NGINX%"=="1"    echo │  [+] Recargar configuracion de Nginx        │
echo └─────────────────────────────────────────────┘
echo.

if defined DRY_RUN goto :dry_run

:: ── Ejecucion ────────────────────────────────────────────────────────────────

:: PASO 1: rebuild de imagen (requirements.txt / Dockerfile / entrypoint.sh)
if "%FLAG_REBUILD%"=="1" (
    echo [1/3] Reconstruyendo imagen del backend...
    call %COMPOSE% build backend celery_worker celery_beat
    if errorlevel 1 goto :compose_error

    echo Levantando servicios con nueva imagen...
    call %COMPOSE% up -d --force-recreate --no-build %BACKEND_SERVICES%
    if errorlevel 1 goto :compose_error
    goto :paso_migraciones
)

:: PASO 1 alt: recrear contenedores (docker-compose / .env)
if "%FLAG_RECREATE%"=="1" (
    echo [1/3] Recreando contenedores...
    call %COMPOSE% up -d --force-recreate --no-build %BACKEND_SERVICES%
    if errorlevel 1 goto :compose_error
    goto :paso_migraciones
)

:: PASO 1 alt: restart rapido de codigo
if "%FLAG_RESTART%"=="1" (
    echo [1/3] Reiniciando backend y Celery con nuevo codigo...
    call %COMPOSE% restart %BACKEND_SERVICES%
    if errorlevel 1 goto :compose_error
)

:paso_migraciones
:: PASO 2: migraciones
if "%FLAG_MIGRATE%"=="1" (
    echo.
    echo [2/3] Ejecutando migraciones de Django...
    call %COMPOSE% exec -T backend python manage.py migrate --noinput
    if errorlevel 1 goto :migrate_error
)

:paso_nginx
:: PASO opcional: recargar Nginx
if "%FLAG_NGINX%"=="1" (
    echo.
    echo [+/3] Recargando configuracion de Nginx...
    call %COMPOSE% exec -T nginx nginx -s reload
    if errorlevel 1 goto :nginx_error
)

goto :success

:dry_run
echo [DRY RUN] Validaciones completadas.
if "%FLAG_REBUILD%"=="1"  echo [DRY RUN] compose build backend celery_worker celery_beat
if "%FLAG_REBUILD%"=="1"  echo [DRY RUN] compose up -d --force-recreate --no-build %BACKEND_SERVICES%
if "%FLAG_RECREATE%"=="1" echo [DRY RUN] compose up -d --force-recreate --no-build %BACKEND_SERVICES%
if "%FLAG_RESTART%"=="1"  echo [DRY RUN] compose restart %BACKEND_SERVICES%
if "%FLAG_MIGRATE%"=="1"  echo [DRY RUN] manage.py migrate --noinput
if "%FLAG_NGINX%"=="1"    echo [DRY RUN] nginx -s reload
goto :success

:sin_cambios
popd
if not defined NO_PAUSE pause
exit /b 0

:usage
echo.
echo Uso:
echo   %~nx0                   deteccion automatica por git
echo   %~nx0 codigo            restart de backend y Celery
echo   %~nx0 build             rebuild de imagen Docker + restart
echo   %~nx0 migraciones       solo ejecuta las migraciones pendientes
echo   %~nx0 nginx             recarga la configuracion de Nginx
echo   %~nx0 todo              rebuild completo + migraciones
echo.
echo Cuando funciona sin rebuild (aplicar.bat o aplicar.bat codigo):
echo   - Cambios en archivos .py (vistas, modelos, serializers, signals, tasks...)
echo   - Cambios en templates HTML
echo   - Cambios en cualquier archivo dentro de backend/
echo.
echo Cuando necesita rebuild (aplicar.bat build):
echo   - Nueva dependencia en requirements.txt
echo   - Cambios en Dockerfile o entrypoint.sh
echo.
echo Cuando necesita recrear contenedores:
echo   - Cambios en docker-compose.yml o .env.dev
echo.
echo No funciona si:
echo   - Agregaste una dependencia sin usar 'build'
echo   - Creaste un modelo sin correr 'makemigrations' antes
echo   - El stack no esta levantado (usa actualizar.bat primero)
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
echo [ERROR] Sincroniza ".env.dev" con "%MAIN_ENV%" o ejecuta desde el repo principal.
goto :fail

:backend_not_running
echo [ERROR] El contenedor backend no esta corriendo.
echo Levanta el stack primero con: actualizar.bat
goto :fail

:compose_error
echo.
echo [ERROR] Fallo al aplicar los cambios. Revisa los mensajes anteriores.
goto :fail

:migrate_error
echo.
echo [ERROR] Fallo al ejecutar las migraciones. Revisa los mensajes anteriores.
goto :fail

:nginx_error
echo.
echo [ERROR] Fallo al recargar Nginx. Revisa la configuracion en nginx/.
goto :fail

:success
echo.
echo Listo. Cambios aplicados correctamente.
echo En el navegador: Ctrl+Shift+R para recarga forzada.
if exist "%CHANGES_FILE%" del "%CHANGES_FILE%" 2>nul
popd
if not defined NO_PAUSE pause
exit /b 0

:fail
if exist "%CHANGES_FILE%" del "%CHANGES_FILE%" 2>nul
popd
if not defined NO_PAUSE pause
exit /b 1
