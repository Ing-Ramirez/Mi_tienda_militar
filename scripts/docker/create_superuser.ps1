param(
    [string]$ProjectName = "mi_tienda_militar",
    [string]$ComposeFile1 = "docker-compose.yml",
    [string]$ComposeFile2 = "docker-compose.dev.yml"
)

$ErrorActionPreference = "Stop"

function ConvertTo-PlainText {
    param([Security.SecureString]$SecureString)

    if ($null -eq $SecureString) {
        return ""
    }

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$email = $env:SUPERUSER_EMAIL
$password = $env:SUPERUSER_PASSWORD

if ([string]::IsNullOrWhiteSpace($email)) {
    $email = Read-Host "Correo del superusuario"
}

if ([string]::IsNullOrWhiteSpace($email)) {
    Write-Error "Debes indicar un correo para el superusuario."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($password)) {
    $passwordSecure = Read-Host "Contrasena del superusuario" -AsSecureString
    $passwordConfirmSecure = Read-Host "Confirma la contrasena" -AsSecureString

    $password = ConvertTo-PlainText $passwordSecure
    $passwordConfirm = ConvertTo-PlainText $passwordConfirmSecure

    if ($password -ne $passwordConfirm) {
        Write-Error "Las contrasenas no coinciden."
        exit 1
    }

    if ([string]::IsNullOrWhiteSpace($password)) {
        Write-Error "La contrasena no puede estar vacia."
        exit 1
    }
}

$env:DJANGO_SUPERUSER_EMAIL = $email
$env:DJANGO_SUPERUSER_PASSWORD = $password

try {
    Write-Host ""
    Write-Host "Creando o actualizando superusuario..."
    & docker compose `
        -p $ProjectName `
        -f $ComposeFile1 `
        -f $ComposeFile2 `
        exec `
        -e DJANGO_SUPERUSER_EMAIL `
        -e DJANGO_SUPERUSER_PASSWORD `
        backend `
        python manage.py ensure_superuser `
        --email-env DJANGO_SUPERUSER_EMAIL `
        --password-env DJANGO_SUPERUSER_PASSWORD

    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:DJANGO_SUPERUSER_EMAIL -ErrorAction SilentlyContinue
    Remove-Item Env:DJANGO_SUPERUSER_PASSWORD -ErrorAction SilentlyContinue
}
