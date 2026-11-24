# =============================================================================
# Habilita acceso SSH entrante seguro sobre Tailscale (100.64.0.0/10) en Windows
# - Auto-eleva permisos de Administrador (UAC) si es necesario
# - Crea regla de Firewall para TCP 22 exclusiva para la red Tailscale (Profile Any)
# - Configura PowerShell como shell predeterminada de OpenSSH
# - Opcionalmente registra una llave pública SSH (compatible con cuentas Admin en Español/Inglés)
# =============================================================================
param(
    [string]$PubKey = ""
)

$ErrorActionPreference = "Stop"

# 1. Verificar privilegios de Administrador; si no, relanzar con UAC
$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[*] Solicitando permisos de Administrador (UAC)..." -ForegroundColor Cyan
    $ArgList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    if ($PubKey) {
        $ArgList += @("-PubKey", "`"$PubKey`"")
    }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $ArgList -Wait
    exit
}

Write-Host "=== Configurando OpenSSH Server para Tailscale ===" -ForegroundColor Cyan

# 2. Asegurar servicio sshd activo y automático
Set-Service -Name sshd -StartupType Automatic
if ((Get-Service -Name sshd).Status -ne "Running") {
    Start-Service -Name sshd
}
Write-Host "[OK] Servicio sshd en ejecución (Automatic)." -ForegroundColor Green

# 3. Crear/actualizar regla de Firewall para Tailscale (100.64.0.0/10) en cualquier perfil (incl. Public)
$RuleName = "OpenSSH-Tailscale-In-TCP"
$ExistingRule = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
if ($ExistingRule) {
    Remove-NetFirewallRule -Name $RuleName
}

New-NetFirewallRule `
    -Name $RuleName `
    -DisplayName "OpenSSH Server (Tailscale 100.64.0.0/10)" `
    -Description "Permite conexiones SSH entrantes exclusivamente desde la red Tailscale en cualquier perfil de red" `
    -Enabled True `
    -Direction Inbound `
    -Protocol TCP `
    -Action Allow `
    -LocalPort 22 `
    -RemoteAddress "100.64.0.0/10" `
    -Profile Any | Out-Null

Write-Host "[OK] Regla de Firewall '$RuleName' activa para 100.64.0.0/10 (Profile: Any)." -ForegroundColor Green

# 4. Configurar PowerShell como shell por defecto al entrar por SSH
if (-not (Test-Path "HKLM:\SOFTWARE\OpenSSH")) {
    New-Item -Path "HKLM:\SOFTWARE\OpenSSH" -Force | Out-Null
}
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" `
    -Name DefaultShell `
    -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -PropertyType String -Force | Out-Null
Write-Host "[OK] Shell por defecto de SSH configurada a PowerShell." -ForegroundColor Green

# 5. Instalar llave pública SSH si fue proporcionada
if ($PubKey.Trim() -ne "") {
    $CleanKey = $PubKey.Trim()
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    # a) authorized_keys del usuario estándar
    $UserSshDir = Join-Path $env:USERPROFILE ".ssh"
    $UserAuthKeys = Join-Path $UserSshDir "authorized_keys"
    New-Item -ItemType Directory -Force -Path $UserSshDir | Out-Null
    $CurrentUserKeys = if (Test-Path $UserAuthKeys) { [System.IO.File]::ReadAllText($UserAuthKeys) } else { "" }
    if ($CurrentUserKeys -notlike "*$CleanKey*") {
        [System.IO.File]::AppendAllText($UserAuthKeys, "$CleanKey`n", $Utf8NoBom)
    }

    # b) administrators_authorized_keys (requerido por Windows OpenSSH para cuentas Administradoras)
    $AdminAuthKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
    $CurrentAdminKeys = if (Test-Path $AdminAuthKeys) { [System.IO.File]::ReadAllText($AdminAuthKeys) } else { "" }
    if ($CurrentAdminKeys -notlike "*$CleanKey*") {
        [System.IO.File]::AppendAllText($AdminAuthKeys, "$CleanKey`n", $Utf8NoBom)
    }

    # Aplicar ACL estricta usando SIDs universales: SYSTEM (S-1-5-18) y Administradores (S-1-5-32-544)
    & icacls.exe $AdminAuthKeys /inheritance:r /grant "*S-1-5-18:(F)" /grant "*S-1-5-32-544:(F)" | Out-Null
    Write-Host "[OK] Llave pública registrada con permisos estrictos en administrators_authorized_keys." -ForegroundColor Green
}

Restart-Service -Name sshd
Write-Host "`n[LISTO] Configuración completada. Presiona Enter para cerrar..." -ForegroundColor Cyan
Read-Host
