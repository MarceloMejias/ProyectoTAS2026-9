# Guía de Puesta en Marcha en Windows (VMware + GNS3)

Al inspeccionar los archivos originales de `ProyectoTAS.tar.gz`, se identificaron **3 detalles de portabilidad** porque el proyecto original fue armado en Linux (`/home/victor/...`). Aquí está cómo levantar todo limpio en Windows:

---

## 1. Importar las Máquinas Virtuales OVF en VMware Workstation

Los archivos `.ovf` y `.mf` de la raíz del repositorio **ya fueron reparados** para no exigir las ISOs de instalación faltantes:

1. En VMware Workstation, ir a **File $\rightarrow$ Open...** e importar como plantillas base:
   - `PC1-WIN.ovf` (Cliente Windows para departamentos)
   - `RockyTAS.ovf` (Base Rocky Linux para `DNSDHCP` y `HTTPS`)
   - `WIN-Server.ovf` (Servidor `ACDC`)
   - *(Para `FirewallSantiago`, importar el OVF/ISO de **pfSense CE 2.7.x** con 3 adaptadores de red `e1000` y 1 GB RAM).*
2. En VMware (**Edit $\rightarrow$ Virtual Network Editor** $\rightarrow$ *Change Settings*):
   - En las redes `VMnet` tipo *Host-only* que utilice GNS3, **desmarcar "Use local DHCP service to distribute IP address to VMs"** para que no compita con el servidor `DNSDHCP` de la DMZ.

> **Nota sobre recursos RAM:** No necesitas encender las 10 VMs al mismo tiempo si tu PC tiene 16 GB de RAM. Para demostrar el 100% del proyecto y la Variante 9 bastan encendidos: `FirewallSantiago`, `DNSDHCP`, `HTTPS`, 1 cliente en Casa Matriz (ej. `Administracion/finanzas` o `TI`) y 2 clientes en Sucursal (`Ventas` y `SoporteTecnico`).

---

## 2. Imagen Cisco IOS (`c2691`) en GNS3

El proyecto utiliza routers Dynamips `c2691` con imagen `c2691-adventerprisek9_sna-mz.124-13b.image`.

- **Si tienes ese mismo archivo `.image`:** cópialo en `C:\Users\<TuUsuario>\GNS3\images\IOS\`.
- **Si tienes otra imagen de `c2691`:** cierra el proyecto en GNS3 y ejecuta:
  ```powershell
  python scripts/fix_gns3_paths.py set-ios "C:\Ruta\A\Tu\c2691-otra-version.image"
  ```

---

## 3. Vincular las VMs en GNS3 (Linked Clones desde Linux)

En `ProyectoTAS.gns3`, los nodos VMware traían rutas de Linux (`/home/victor/GNS3/projects/...`). En Windows:
1. En GNS3 ve a **Edit $\rightarrow$ Preferences $\rightarrow$ VMware VMs $\rightarrow$ New**.
2. Registra tus plantillas importadas (`PC1-WIN`, `RockyTAS`, `WIN-Server`, `pfSense`) marcando **"Allow GNS3 to override non custom VMware adapter"** (y opcionalmente *Use as a linked base VM* para ahorrar disco al crear varios clientes `PC1-WIN`).
3. Reemplaza los nodos VMware del lienzo por tus plantillas locales respetando las conexiones a `SwitchAccesoS`, `SwitchAccesoV` y `SwitchDMZ`.

---

## 4. Agregar el Segundo Enlace WAN (Variante 9) y Cargar Configs

1. Con el proyecto cerrado en GNS3, agrega automáticamente el enlace de respaldo (`Santiago Fa1/0 <-> Vina Fa0/1`):
   ```powershell
   python scripts/fix_gns3_paths.py add-backup-link
   ```
   *(O conéctalo manualmente en GNS3 con la herramienta de cable entre `Santiago FastEthernet1/0` y `Vina FastEthernet0/1`).*
2. Abre el proyecto en GNS3, enciende `Santiago` y `Vina`, y aplica las configuraciones automáticamente:
   ```powershell
   python scripts/gns3_control.py push-configs
   python scripts/gns3_control.py routes
   ```
3. En las VMs Linux de la DMZ, copia o ejecuta los scripts:
   - En `DNSDHCP`: `sudo bash setup_dns_dhcp_rocky.sh`
   - En `HTTPS`: `sudo bash setup_https_rocky.sh`
4. Configura `FirewallSantiago` siguiendo `configs/firewall/pfsense_guia_config.md`.
