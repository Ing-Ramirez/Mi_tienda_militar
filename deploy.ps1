param(
    [string]$Mensaje = "",
    [string]$Rama = "main"
)

$ErrorActionPreference = "Stop"

function Linea { Write-Host "  -------------------------------------------" -ForegroundColor DarkGray }
function Ok($t)   { Write-Host "  OK: $t" -ForegroundColor Green }
function Info($t) { Write-Host "  >> $t" -ForegroundColor Cyan }
function Warn($t) { Write-Host "  !! $t" -ForegroundColor Yellow }

Clear-Host
Write-Host ""
Write-Host "  FRANJA PIXELADA - DEPLOY GIT" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path ".git")) {
    Write-Host "  ERROR: No hay repositorio Git aqui." -ForegroundColor Red
    exit 1
}

# 1. Estado
Linea
Info "1/5  ESTADO DEL REPOSITORIO"
Linea
$cambios = git status --short
if (-not $cambios) {
    Warn "No hay cambios pendientes. Repositorio limpio."
    exit 0
}
$cambios | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

# 2. Mensaje
Linea
Info "2/5  MENSAJE DEL COMMIT"
Linea
if (-not $Mensaje) {
    $fecha = Get-Date -Format "yyyy-MM-dd HH:mm"
    $default = "chore: actualizacion general $fecha"
    Write-Host "  Escribe el mensaje (Enter para usar predeterminado):" -ForegroundColor White
    Write-Host "  > " -NoNewline -ForegroundColor Cyan
    $respuesta = Read-Host
    if ($respuesta.Trim()) { $Mensaje = $respuesta.Trim() } else { $Mensaje = $default }
}
Ok $Mensaje

# 3. Staging
Linea
Info "3/5  STAGING"
Linea
git add .
Ok "Archivos agregados."

# 4. Commit
Linea
Info "4/5  COMMIT"
Linea
$staged = git diff --cached --name-only
if (-not $staged) {
    Warn "Nada en staging. Ya estaba commiteado."
} else {
    git commit -m $Mensaje
    $hash = git rev-parse --short HEAD
    Ok "Commit creado: $hash"
}

# 5. Pull
Linea
Info "5/6  PULL --REBASE"
Linea
git pull --rebase origin $Rama
Ok "Pull exitoso."

# 6. Push
Linea
Info "6/6  PUSH"
Linea
git push origin $Rama
Ok "Push exitoso."

# Resumen
Write-Host ""
Write-Host "  DESPLIEGUE COMPLETADO" -ForegroundColor Green
Write-Host ""
$ultimo = git log --oneline -1
Info "Rama   : $Rama"
Write-Host "  >> Commit : $ultimo" -ForegroundColor Cyan
Write-Host ""
