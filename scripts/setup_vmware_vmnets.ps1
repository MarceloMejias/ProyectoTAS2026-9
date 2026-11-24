# =============================================================================
# Soluciona la incompatibilidad entre GNS3 2.2 y VMware Workstation 26 (64-bit)
# y crea automáticamente los adaptadores Host-only VMnet2..VMnet15 (sin VMnet8):
#   1. Auto-eleva permisos de Administrador (UAC).
#   2. Copia claves de registro de 64-bit a WOW6432Node y crea vnetlib64.exe.
#   3. Ejecuta gns3vmnet.exe -r 2 15 (con respaldo directo a vnetlib.exe).
#   4. Muestra los adaptadores VMnet creados y activos en Windows.
# =============================================================================
$ErrorActionPreference = "Stop"

# 1. Auto-elevar a Administrador (UAC)
$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[*] Solicitando permisos de Administrador (UAC) para crear adaptadores VMnet..." -ForegroundColor Cyan
    Start-Process powershell.exe -Verb RunAs -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"") -Wait
    exit
}

$VmwareDir = "C:\Program Files\VMware\VMware Workstation"
$VnetLib = Join-Path $VmwareDir "vnetlib.exe"
$VnetLib64 = Join-Path $VmwareDir "vnetlib64.exe"
$Gns3Vmnet = "C:\Program Files\GNS3\gns3vmnet.exe"

Write-Host "=== 1. Aplicando compatibilidad VMware 26 (64-bit) para GNS3 ===" -ForegroundColor Cyan
if ((Test-Path $VnetLib) -and -not (Test-Path $VnetLib64)) {
    Copy-Item -Force $VnetLib $VnetLib64
    Write-Host "[OK] Creado $VnetLib64" -ForegroundColor Green
}

# Registrar claves en WOW6432Node donde GNS3 2.2 y gns3vmnet buscan VMware Workstation
$WowBase = "HKLM:\SOFTWARE\WOW6432Node\VMware, Inc."
$WowWs = "$WowBase\VMware Workstation"
New-Item -Path $WowWs -Force | Out-Null
Set-ItemProperty -Path $WowBase -Name "(Default)" -Value "VMware Workstation" -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $WowBase -Name "Core" -Value "VMware Workstation" -Force
Set-ItemProperty -Path $WowWs -Name "InstallPath" -Value "$VmwareDir\" -Force
Set-ItemProperty -Path $WowWs -Name "InstallPath64" -Value "$VmwareDir\" -Force

if (Test-Path "HKLM:\SOFTWARE\VMware, Inc.\VMware Workstation") {
    $Props64 = Get-ItemProperty "HKLM:\SOFTWARE\VMware, Inc.\VMware Workstation"
    foreach ($p in $Props64.PSObject.Properties) {
        if ($p.Name -notlike "PS*") {
            Set-ItemProperty -Path $WowWs -Name $p.Name -Value $p.Value -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "[OK] Claves de registro WOW6432Node sincronizadas." -ForegroundColor Green

Write-Host "`n=== 2. Creando interfaces Host-only VMnet2..VMnet15 (excluyendo VMnet8) ===" -ForegroundColor Cyan
if (Test-Path $Gns3Vmnet) {
    try {
        & $Gns3Vmnet -r 2 15
    } catch {
        Write-Warning "gns3vmnet reportó un aviso: $_"
    }
}

# Verificar si VMnet2 existe; si no, crear cada interfaz directamente con vnetlib.exe
$CheckVmnet2 = Get-NetAdapter -Name "*VMnet2*" -ErrorAction SilentlyContinue
if (-not $CheckVmnet2) {
    Write-Host "[*] Creando adaptadores directamente con vnetlib.exe (puede tardar ~1 minuto)..." -ForegroundColor Yellow
    foreach ($i in 2..15) {
        if ($i -eq 8) { continue }
        $vnet = "vmnet$i"
        Write-Host "  -> Creando $vnet..."
        & $VnetLib -- add adapter $vnet | Out-Null
        & $VnetLib -- set vnet $vnet addr "172.16.$i.0" | Out-Null
        & $VnetLib -- set vnet $vnet mask "255.255.255.0" | Out-Null
        & $VnetLib -- remove dhcp $vnet | Out-Null
        & $VnetLib -- remove nat $vnet | Out-Null
        & $VnetLib -- update adapter $vnet | Out-Null
    }
}

Write-Host "`n=== 3. Adaptadores VMnet activos en Windows ===" -ForegroundColor Cyan
Get-NetAdapter *VMnet* | Sort-Object Name | Format-Table Name, InterfaceDescription, Status -AutoSize

Write-Host "[LISTO] Reinicia GNS3 (ciérralo y vuelve a abrirlo) para que refresque la lista de VMnets." -ForegroundColor Green
Read-Host "Presiona Enter para cerrar"
