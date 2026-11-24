# Guía de Puesta en Marcha en Windows (VMware + GNS3 — Equipo 1)

---

## 1. Configurar `vmrun.exe` en GNS3 (VMware Workstation 64-bit)

En **Edit $\rightarrow$ Preferences $\rightarrow$ VMware**:
- **Path to vmrun:** `C:\Program Files\VMware\VMware Workstation\vmrun.exe`
- En **Advanced local settings**, hacer clic en **Configure** para habilitar las interfaces `VMnet` de GNS3.
- En VMware (**Edit $\rightarrow$ Virtual Network Editor**), desmarcar *"Use local DHCP service"* en las redes *Host-only* usadas por GNS3 para que no compitan con `DNSDHCP`.

---

## 2. Imágenes Cisco IOS y Máquinas Virtuales

- **Routers (`Santiago` y `Vina`/`Valparaiso`):** Usan `images/c2691-adventerprisek9_sna-mz.124-13b.image` (ya copiada en `project-files/images/`).
- **Plantillas en `vmware/`:**
  - `vmware/pfSense/FirewallSantiago.vmx`: VM lista con 1 GB RAM, disco de 8 GB, 3 tarjetas `e1000` e ISO `images/pfSense-CE-2.7.0-RELEASE-amd64.iso` montada (instalar pfSense una vez, apagar y desconectar el CD/DVD).
  - `vmware/RockyTAS/RockyTAS.ovf`: Base Rocky Linux para `DNSDHCP` y `HTTPS` *(puedes bajarles la RAM de 2048 MB a **768 MB** para ahorrar recursos)*.
  - `vmware/PC1-WIN/PC1-WIN.ovf`: Cliente Windows departamental *(basta encender **1 sola instancia** para pruebas con navegador)*.
  - `vmware/WIN-Server/WIN-Server.ovf`: Servidor `ACDC` *(opcional mantenerlo apagado para ahorrar ~4 GB de RAM)*.

---

## 3. Flujo de Pruebas por Etapas (Sin Quemar RAM)

> **Importante:** Nunca presiones *"Start/Resume all nodes"* en GNS3. Enciende solo los equipos de cada etapa.

### Etapa A — Prueba Instantánea con 0 VMs (~400 MB RAM)
Valida VLANs, `ip helper-address`, 2 ámbitos DHCP remotos, ACLs y renovación en menos de 1 minuto usando únicamente `Santiago`, `Valparaiso`, switches y 2 nodos `VPCS` livianos:

```powershell
uv run python scripts/gns3_control.py push-configs
uv run python scripts/demo_variante1.py --simular-servidor --auto
```

### Etapa B — Servicios Reales en DMZ (`FirewallSantiago` + `DNSDHCP` + `HTTPS` ~2.5 GB RAM)
1. Configura `FirewallSantiago` siguiendo `configs/firewall/pfsense_guia_config.md`.
2. En la VM `DNSDHCP` ejecuta: `sudo bash setup_dns_dhcp_rocky.sh`
3. En la VM `HTTPS` ejecuta: `sudo bash setup_https_rocky.sh`
4. Ejecuta la prueba real de los 2 ámbitos desde Sucursal:
   ```powershell
   uv run python scripts/demo_variante1.py
   ```
   *(Cuando el script te lo indique, corre `sudo bash cambiar_opcion_ambito_dhcp.sh 192.168.0.35` en `DNSDHCP` para demostrar el cambio de opción y renovación en vivo).*
