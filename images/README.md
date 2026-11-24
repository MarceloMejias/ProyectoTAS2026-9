# Imágenes Cisco IOS para GNS3

Esta carpeta almacena localmente las imágenes IOS requeridas por Dynamips en GNS3 (los binarios `*.image` y `*.bin` están excluidos de Git en `.gitignore`):

| Archivo | Plataforma | Uso en el Proyecto |
| :--- | :--- | :--- |
| `c2691-adventerprisek9_sna-mz.124-13b.image` | Cisco `c2691` | Routers `Santiago` y `Vina` / `Valparaiso` (`MD5: 0b25113b4d92306aa4edc2e03fa52e82`) |
| `c7200-advipservicesk9-mz.152-4.S5.bin` | Cisco `c7200` | Imagen alternativa / de respaldo |

## Instalación rápida en GNS3

Desde la raíz del repositorio ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_gns3_images.ps1
```

Esto copia automáticamente las imágenes tanto a `gns3/ProyectoTAS/ProyectoTAS/project-files/images/` como al directorio global `%USERPROFILE%\GNS3\images\IOS\`.
