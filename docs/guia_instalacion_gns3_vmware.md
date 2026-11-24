# Guía de Puesta en Marcha en Windows (VMware + GNS3)

Al inspeccionar los archivos originales de `ProyectoTAS.tar.gz`, se identificaron **3 detalles de portabilidad** porque el proyecto original fue armado en Linux (`/home/victor/...`). Aquí está cómo levantar todo limpio en Windows:

---

## 1. Importar las Máquinas Virtuales OVF en VMware Workstation

Los archivos `.ovf` y `.mf` dentro de la carpeta `vmware/` **ya fueron reparados** para no exigir las ISOs de instalación faltantes:

1. En VMware Workstation, ir a **File $\rightarrow$ Open...** e importar como plantillas base:
   - `vmware/PC1-WIN/PC1-WIN.ovf` (Cliente Windows para departamentos)
   - `vmware/RockyTAS/RockyTAS.ovf` (Base Rocky Linux para `DNSDHCP` y `HTTPS`)
   - `vmware/WIN-Server/WIN-Server.ovf` (Servidor `ACDC`)
   - `vmware/pfSense/FirewallSantiago.vmx` (**ya generada** con 1 GB RAM, disco de 8 GB, 3 adaptadores `e1000` e ISO `images/pfSense-CE-2.7.0-RELEASE-amd64.iso` montada: ábrela en VMware, instala pfSense con valores por defecto —ZFS o UFS—, apágala y desconecta el CD/DVD en *VM Settings* para que arranque desde el disco).
2. En VMware (**Edit $\rightarrow$ Virtual Network Editor** $\rightarrow$ *Change Settings*):
   - En las redes `VMnet` tipo *Host-only* que utilice GNS3, **desmarcar "Use local DHCP service to distribute IP address to VMs"** para que no compita con el servidor `DNSDHCP` de la DMZ.

> **Nota sobre recursos RAM:** No necesitas encender las 10 VMs al mismo tiempo si tu PC tiene 16 GB de RAM. Para demostrar el 100% del proyecto y la Variante 9 bastan encendidos: `FirewallSantiago`, `DNSDHCP`, `HTTPS`, 1 cliente en Casa Matriz (ej. `Administracion/finanzas` o `TI`) y 2 clientes en Sucursal (`Ventas` y `SoporteTecnico`).

---

## 2. Imagen Cisco IOS (`c2691`) en GNS3

Las imágenes requeridas (`c2691-adventerprisek9_sna-mz.124-13b.image` con MD5 exacto `0b25113b4d92306aa4edc2e03fa52e82`, y `c7200-advipservicesk9-mz.152-4.S5.bin`) se encuentran en la carpeta `images/`.

- Ya fueron copiadas dentro de `gns3/ProyectoTAS/ProyectoTAS/project-files/images/` para que el proyecto abra directamente.
- Para instalarlas también en tu carpeta global `%USERPROFILE%\GNS3\images\IOS\`, ejecuta:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/install_gns3_images.ps1
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
