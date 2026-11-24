# =============================================================================
# Crea la máquina virtual VMware lista para instalar y usar como FirewallSantiago
# en vmware/pfSense/ usando images/pfSense-CE-2.7.0-RELEASE-amd64.iso
# =============================================================================
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$IsoPath = Join-Path $RepoRoot "images\pfSense-CE-2.7.0-RELEASE-amd64.iso"
$VmDir = Join-Path $RepoRoot "vmware\pfSense"
$VmxPath = Join-Path $VmDir "FirewallSantiago.vmx"
$VmdkDescPath = Join-Path $VmDir "FirewallSantiago.vmdk"
$VmdkFlatPath = Join-Path $VmDir "FirewallSantiago-flat.vmdk"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path $IsoPath)) {
    Write-Error "No se encontró la ISO de pfSense en: $IsoPath"
}

New-Item -ItemType Directory -Force -Path $VmDir | Out-Null

# 1. Crear disco plano disperso NTFS de 8 GB (ocupa ~0 MB en disco hasta escribir datos)
$DiskSizeBytes = 8GB
$Sectors = [int64]($DiskSizeBytes / 512) # 16777216 sectores

if (-not (Test-Path $VmdkFlatPath)) {
    $fs = [System.IO.File]::Open($VmdkFlatPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::ReadWrite)
    $fs.Close()
    & fsutil sparse setflag $VmdkFlatPath | Out-Null
    $fs = [System.IO.File]::Open($VmdkFlatPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite)
    $fs.SetLength($DiskSizeBytes)
    $fs.Close()
    Write-Host "[OK] Disco virtual disperso creado (8 GB lógicos): $VmdkFlatPath"
}

# 2. Crear descriptor VMDK
$VmdkDescriptor = @"
# Disk DescriptorFile
version=1
encoding="UTF-8"
CID=fffffffe
parentCID=ffffffff
isNativeSnapshot="no"
createType="monolithicFlat"

# Extent description
RW $Sectors FLAT "FirewallSantiago-flat.vmdk" 0

# The Disk Data Base
#DDB
ddb.adapterType = "lsilogic"
ddb.geometry.cylinders = "1044"
ddb.geometry.heads = "255"
ddb.geometry.sectors = "63"
ddb.virtualHWVersion = "19"
"@ -replace "`r`n", "`n"
[System.IO.File]::WriteAllText($VmdkDescPath, $VmdkDescriptor, $Utf8NoBom)

# 3. Crear archivo FirewallSantiago.vmx con 3 adaptadores e1000 e ISO montada
$VmxContent = @"
.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "19"
pciBridge0.present = "TRUE"
pciBridge4.present = "TRUE"
pciBridge4.virtualDev = "pcieRootPort"
pciBridge4.functions = "8"
pciBridge5.present = "TRUE"
pciBridge5.virtualDev = "pcieRootPort"
pciBridge5.functions = "8"
pciBridge6.present = "TRUE"
pciBridge6.virtualDev = "pcieRootPort"
pciBridge6.functions = "8"
pciBridge7.present = "TRUE"
pciBridge7.virtualDev = "pcieRootPort"
pciBridge7.functions = "8"
vmci0.present = "TRUE"
hpet0.present = "TRUE"
displayName = "FirewallSantiago"
guestOS = "freebsd-64"
memsize = "1024"
numvcpus = "1"
scsi0.virtualDev = "lsilogic"
scsi0.present = "TRUE"
scsi0:0.present = "TRUE"
scsi0:0.fileName = "FirewallSantiago.vmdk"
ide1:0.present = "TRUE"
ide1:0.deviceType = "cdrom-image"
ide1:0.fileName = "$IsoPath"
ide1:0.startConnected = "TRUE"
ethernet0.present = "TRUE"
ethernet0.connectionType = "hostonly"
ethernet0.virtualDev = "e1000"
ethernet0.addressType = "generated"
ethernet1.present = "TRUE"
ethernet1.connectionType = "hostonly"
ethernet1.virtualDev = "e1000"
ethernet1.addressType = "generated"
ethernet2.present = "TRUE"
ethernet2.connectionType = "hostonly"
ethernet2.virtualDev = "e1000"
ethernet2.addressType = "generated"
powerType.powerOff = "soft"
powerType.powerOn = "soft"
powerType.suspend = "soft"
powerType.reset = "soft"
"@ -replace "`r`n", "`n"
[System.IO.File]::WriteAllText($VmxPath, $VmxContent, $Utf8NoBom)

Write-Host "[OK] VM pfSense lista en: $VmxPath"
