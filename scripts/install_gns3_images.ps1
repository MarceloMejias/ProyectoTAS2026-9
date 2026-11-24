# =============================================================================
# Instala las imágenes Cisco IOS de ./images en el proyecto GNS3 y en el perfil
# global de GNS3 (%USERPROFILE%\GNS3\images\IOS)
# =============================================================================
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SourceDir = Join-Path $RepoRoot "images"
$ProjectImagesDir = Join-Path $RepoRoot "gns3\ProyectoTAS\ProyectoTAS\project-files\images"
$GlobalIosDir = Join-Path $env:USERPROFILE "GNS3\images\IOS"

$Images = Get-ChildItem -Path $SourceDir -Include "*.image", "*.bin" -Recurse
if (-not $Images) {
    Write-Error "No se encontraron archivos .image o .bin en $SourceDir"
}

if (Test-Path (Split-Path -Parent $ProjectImagesDir)) {
    New-Item -ItemType Directory -Force -Path $ProjectImagesDir | Out-Null
    foreach ($img in $Images) {
        Copy-Item -Force -Path $img.FullName -Destination $ProjectImagesDir
        Write-Host "[OK] Copiado al proyecto GNS3: $($img.Name)"
    }
}

New-Item -ItemType Directory -Force -Path $GlobalIosDir | Out-Null
foreach ($img in $Images) {
    Copy-Item -Force -Path $img.FullName -Destination $GlobalIosDir
    Write-Host "[OK] Copiado a GNS3 global ($GlobalIosDir): $($img.Name)"
}
