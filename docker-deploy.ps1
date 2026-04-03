param(
    [switch]$Rebuild,
    [switch]$FullRestart
)

$ErrorActionPreference = "Stop"

function Linea { Write-Host "  -------------------------------------------" -ForegroundColor DarkGray }
function Ok($t)   { Write-Host "  OK: $t" -ForegroundColor Green }
function Info($t) { Write-Host "  >> $t" -ForegroundColor Cyan }
function Warn($t) { Write-Host "  !! $t" -ForegroundColor Yellow }
function Err($t)  { Write-Host "  ERROR: $t" -ForegroundColor Red }

function EsperarBackendSano {
    Info "Esperando que el backend este healthy..."
    $intentos = 0
    do {
        Start-Sleep -Seconds 5
        $estado = docker inspect --format="{{.State.Health.Status}}" franja_pixelada_backend 2>$null
        $intentos++
        Write-Host "    intento $intentos - estado: $estado" -ForegroundColor DarkGray
    } while ($estado -ne "healthy" -and $intentos -lt 24)

    if ($estado -ne "healthy") {
        Err "El backend no alcanzo estado healthy despues de 2 minutos."
        Err "Revisa los logs: docker-compose logs backend"
        exit 1
    }
    Ok "Backend healthy."
}

Clear-Host
Write-Host ""
Write-Host "  FRANJA PIXELADA - DOCKER DEPLOY" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path "docker-compose.yml")) {
    Err "No se encontro docker-compose.yml en este directorio."
    exit 1
}

if ($Rebuild) {
    Write-Host "  Modo: REBUILD COMPLETO (--no-cache)" -ForegroundColor Yellow
} elseif ($FullRestart) {
    Write-Host "  Modo: RESTART COMPLETO (down + up)" -ForegroundColor Yellow
} else {
    Write-Host "  Modo: ACTUALIZACION RAPIDA (restart)" -ForegroundColor Cyan
}
Write-Host ""

# 1. Estado inicial
Linea
Info "1/5  ESTADO DE CONTENEDORES"
Linea
docker-compose ps
Write-Host ""

# 2. Build (solo si -Rebuild)
if ($Rebuild) {
    Linea
    Info "2/5  REBUILD DE IMAGENES (backend + celery)"
    Linea
    Warn "Esto puede tardar varios minutos..."
    <#
      La misma Dockerfile alimenta backend y Celery. Reconstruir solo backend deja
      worker/beat con imagen desactualizada.
    #>
    docker-compose build --no-cache backend celery_worker celery_beat
    Ok "Imagenes reconstruidas."
} else {
    Linea
    Info "2/5  BUILD (omitido)"
    Linea
    Warn "Usando imagen existente. Agrega -Rebuild para reconstruir."
}

# 3. Levantar / reiniciar servicios
Linea
Info "3/5  SERVICIOS DOCKER"
Linea
if ($FullRestart) {
    Warn "Bajando todos los contenedores..."
    docker-compose down
    Info "Levantando stack (db, redis, backend, celery, nginx)..."
    docker-compose up -d
    Ok "Stack completo levantado."
    EsperarBackendSano
} elseif ($Rebuild) {
    <#
      - `docker-compose restart` NO aplica una imagen recien construida (reinicia el mismo contenedor).
      - Si el stack no estaba levantado, `restart` no abre el puerto 80 => ERR_CONNECTION_REFUSED en localhost.
      - `up -d --force-recreate` recrea backend/celery con la nueva imagen; luego nginx una vez el backend es healthy.
    #>
    Info "Recreando contenedores (nueva imagen) y asegurando nginx en :80..."
    docker-compose up -d --force-recreate backend celery_worker celery_beat
    EsperarBackendSano
    docker-compose up -d nginx
    Ok "Backend, Celery y Nginx listos."
} else {
    docker-compose restart backend celery_worker celery_beat
    Ok "Backend, Celery worker y Celery beat reiniciados."
    EsperarBackendSano
    Info "Reconectando Nginx al backend..."
    docker-compose restart nginx
    Ok "Nginx reconectado."
}

# 4. Migraciones
Linea
Info "4/5  MIGRACIONES"
Linea
docker-compose exec backend python manage.py migrate
Ok "Migraciones aplicadas."

# 5. Archivos estaticos
Linea
Info "5/5  ARCHIVOS ESTATICOS"
Linea
docker-compose exec backend python manage.py collectstatic --no-input
Ok "Estaticos recolectados."

# Estado final
Linea
Write-Host ""
Write-Host "  ACTUALIZACION DOCKER COMPLETADA" -ForegroundColor Green
Write-Host ""
docker-compose ps
Write-Host ""
Info "Tienda: http://localhost/"
Info "Admin (defecto): http://localhost/admin/"
Warn "Si persiste ERR_CONNECTION_REFUSED: comprobar Docker Desktop, y que ningun otro servicio use el puerto 80 (IIS, World Wide Web Publishing, etc.)."
Write-Host ""
