<# 
Port guard for docker-compose.
Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\port_guard.ps1 init
  powershell -ExecutionPolicy Bypass -File .\scripts\port_guard.ps1 randomize
  powershell -ExecutionPolicy Bypass -File .\scripts\port_guard.ps1 show
Notes:
  - Default refuses to randomize container ports 80/443. Use -AllowPublicPorts to override.
  - This script only edits docker-compose ports. It does NOT change Windows system services.
#>

[CmdletBinding()]
param(
    [ValidateSet('init','randomize','show')]
    [string]$Action = 'show',
    [string]$ComposePath = 'docker-compose.yml',
    [string]$Service = 'nginx',
    [int]$PortMin = 20000,
    [int]$PortMax = 50000,
    [switch]$AllowPublicPorts,
    [switch]$NoConfirm
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$secretPath = Join-Path $scriptDir '.port_guard.secret'
$mapPath = Join-Path $scriptDir '.port_guard.map'

function Convert-SecureStringToPlain {
    param([SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Confirm-Action {
    param([string]$Message)
    if ($NoConfirm) { return $true }
    $resp = Read-Host $Message
    return ($resp -eq 'SI')
}

function Read-StoredSecretPlain {
    if (-not (Test-Path -LiteralPath $secretPath)) {
        throw "No secret found. Run: powershell -File .\scripts\port_guard.ps1 init"
    }
    $enc = Get-Content -LiteralPath $secretPath -Raw
    $ss = ConvertTo-SecureString $enc
    return Convert-SecureStringToPlain $ss
}

function Verify-Secret {
    $input = Read-Host 'Clave' -AsSecureString
    $inputPlain = Convert-SecureStringToPlain $input
    $storedPlain = Read-StoredSecretPlain
    $ok = ($inputPlain -eq $storedPlain)
    $inputPlain = $null
    $storedPlain = $null
    if (-not $ok) { throw 'Clave incorrecta.' }
}

function Init-Secret {
    if ((Test-Path -LiteralPath $secretPath) -and (-not (Confirm-Action 'Ya existe una clave. Escribe SI para reemplazarla'))) {
        Write-Host 'Cancelado.'
        return
    }
    $first = Read-Host 'Crea una clave' -AsSecureString
    $second = Read-Host 'Repite la clave' -AsSecureString
    $p1 = Convert-SecureStringToPlain $first
    $p2 = Convert-SecureStringToPlain $second
    if ($p1 -ne $p2) { throw 'Las claves no coinciden.' }
    $enc = $first | ConvertFrom-SecureString
    Set-Content -LiteralPath $secretPath -Value $enc -NoNewline
    try {
        icacls $secretPath /inheritance:r /grant "$env:USERNAME:(R,W)" | Out-Null
    } catch {
        Write-Warning 'No se pudieron ajustar permisos del archivo de clave.'
    }
    Write-Host 'OK. Clave guardada.'
}

function Get-ComposeText {
    $fullPath = (Resolve-Path -LiteralPath $ComposePath).Path
    $bytes = [System.IO.File]::ReadAllBytes($fullPath)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $encoding = New-Object System.Text.UTF8Encoding($hasBom)
    if ($hasBom) {
        $text = $encoding.GetString($bytes, 3, $bytes.Length - 3)
    } else {
        $text = $encoding.GetString($bytes)
    }
    return [pscustomobject]@{ Path = $fullPath; Text = $text; Encoding = $encoding }
}

function Save-ComposeText {
    param([string]$Path, [string]$Text, [System.Text.Encoding]$Encoding)
    [System.IO.File]::WriteAllText($Path, $Text, $Encoding)
}

function Find-ServiceBlock {
    param([string[]]$Lines, [string]$ServiceName)
    $servicePattern = "^\s{2}$([Regex]::Escape($ServiceName)):\s*$"
    $start = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $servicePattern) { $start = $i; break }
    }
    if ($start -lt 0) { throw "Service '$ServiceName' not found in compose file." }

    $end = $Lines.Count - 1
    for ($i = $start + 1; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match '^\s{2}[A-Za-z0-9_-]+:\s*$') {
            $end = $i - 1
            break
        }
    }
    return @($start, $end)
}

function Parse-PortLine {
    param([string]$Line)
    $trim = $Line.Trim()
    $quoted = ($trim -match '"')
    $indent = ($Line -replace '^(\s*).*$','$1')

    if ($trim -match '^- "?(\[[^\]]+\]):(\d+):(\d+)"?$') {
        return [pscustomobject]@{ Indent=$indent; Quoted=$quoted; Ip=$matches[1]; Host=$matches[2]; Container=$matches[3] }
    }
    if ($trim -match '^- "?([0-9\.]+):(\d+):(\d+)"?$') {
        return [pscustomobject]@{ Indent=$indent; Quoted=$quoted; Ip=$matches[1]; Host=$matches[2]; Container=$matches[3] }
    }
    if ($trim -match '^- "?(\d+):(\d+)"?$') {
        return [pscustomobject]@{ Indent=$indent; Quoted=$quoted; Ip=$null; Host=$matches[1]; Container=$matches[2] }
    }
    return $null
}

function Format-PortLine {
    param([string]$Indent, [string]$Ip, [string]$Host, [string]$Container, [bool]$Quoted)
    $map = if ($Ip) { "$Ip`:$Host`:$Container" } else { "$Host`:$Container" }
    $out = if ($Quoted) { "- `"$map`"" } else { "- $map" }
    return "$Indent$out"
}

function Get-UsedPorts {
    try {
        return Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty LocalPort -Unique
    } catch {
        return @()
    }
}

function Get-RandomFreePort {
    param([int]$Min, [int]$Max, [int[]]$Used)
    for ($i = 0; $i -lt 200; $i++) {
        $candidate = Get-Random -Minimum $Min -Maximum ($Max + 1)
        if ($Used -notcontains $candidate) { return $candidate }
    }
    throw 'No free port found in range.'
}

function Randomize-ComposePorts {
    Verify-Secret

    $compose = Get-ComposeText
    $lineEnding = if ($compose.Text -match "`r`n") { "`r`n" } else { "`n" }
    $lines = $compose.Text -split "`r?`n"
    $range = Find-ServiceBlock -Lines $lines -ServiceName $Service
    $start = $range[0]
    $end = $range[1]

    $portsLine = -1
    for ($i = $start + 1; $i -le $end; $i++) {
        if ($lines[$i] -match '^\s{4}ports:\s*$') { $portsLine = $i; break }
    }
    if ($portsLine -lt 0) { throw "No ports: block found for service '$Service'." }

    $portItems = @()
    for ($i = $portsLine + 1; $i -le $end; $i++) {
        if ($lines[$i] -notmatch '^\s{6}-') { break }
        $parsed = Parse-PortLine -Line $lines[$i]
        if (-not $parsed) { throw "Unsupported port format: $($lines[$i])" }
        $portItems += [pscustomobject]@{ Index=$i; Data=$parsed }
    }
    if ($portItems.Count -eq 0) { throw "No port mappings found under ports: for service '$Service'." }

    foreach ($item in $portItems) {
        $c = [int]$item.Data.Container
        if ((-not $AllowPublicPorts) -and ($c -eq 80 -or $c -eq 443)) {
            throw "Refusing to randomize container port $c. Use -AllowPublicPorts if you are sure."
        }
    }

    if (-not (Confirm-Action "Escribe SI para cambiar los puertos publicados en '$ComposePath'")) {
        Write-Host 'Cancelado.'
        return
    }

    $used = @(Get-UsedPorts)
    $mapping = @()
    foreach ($item in $portItems) {
        $newHost = Get-RandomFreePort -Min $PortMin -Max $PortMax -Used $used
        $used += $newHost
        $oldHost = [int]$item.Data.Host
        $item.Data.Host = $newHost
        $lines[$item.Index] = Format-PortLine -Indent $item.Data.Indent -Ip $item.Data.Ip -Host $item.Data.Host -Container $item.Data.Container -Quoted $item.Data.Quoted
        $mapping += [pscustomobject]@{
            old_host = $oldHost
            new_host = $newHost
            container = [int]$item.Data.Container
            ip = $item.Data.Ip
        }
    }

    $newText = $lines -join $lineEnding
    Save-ComposeText -Path $compose.Path -Text $newText -Encoding $compose.Encoding

    $mapObj = [pscustomobject]@{
        updated_at = (Get-Date).ToString('s')
        service = $Service
        compose_path = $compose.Path
        ports = $mapping
    }
    $json = $mapObj | ConvertTo-Json -Depth 5
    $secure = ConvertTo-SecureString $json -AsPlainText -Force
    $enc = $secure | ConvertFrom-SecureString
    Set-Content -LiteralPath $mapPath -Value $enc -NoNewline
    try {
        icacls $mapPath /inheritance:r /grant "$env:USERNAME:(R,W)" | Out-Null
    } catch {
        Write-Warning 'No se pudieron ajustar permisos del archivo de mapa.'
    }

    Write-Host 'OK. Puertos actualizados en compose.'
}

function Show-Ports {
    Verify-Secret
    if (-not (Test-Path -LiteralPath $mapPath)) { throw 'No hay mapa guardado. Ejecuta randomize primero.' }
    $enc = Get-Content -LiteralPath $mapPath -Raw
    $ss = ConvertTo-SecureString $enc
    $plain = Convert-SecureStringToPlain $ss
    $data = $plain | ConvertFrom-Json
    Write-Host "Servicio: $($data.service)"
    Write-Host "Compose:  $($data.compose_path)"
    Write-Host "Fecha:    $($data.updated_at)"
    Write-Host 'Puertos:'
    foreach ($p in $data.ports) {
        $ip = if ($p.ip) { "$($p.ip) " } else { '' }
        Write-Host "  $ip$($p.new_host) -> $($p.container) (antes $($p.old_host))"
    }
}

switch ($Action) {
    'init' { Init-Secret }
    'randomize' { Randomize-ComposePorts }
    'show' { Show-Ports }
}
