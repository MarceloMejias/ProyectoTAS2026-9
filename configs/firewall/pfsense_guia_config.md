# Configuración de `FirewallSantiago` (pfSense)

En la topología GNS3, `FirewallSantiago` tiene 3 adaptadores (`e0`, `e1`, `e2` / `em0`, `em1`, `em2` en FreeBSD):

| Adaptador GNS3 | Interfaz pfSense | Conectado a | Subred / VLAN | IP de pfSense |
| :--- | :--- | :--- | :--- | :--- |
| `e0` | `em0` (WAN / Tránsito) | `Santiago Fa0/1` | `192.168.0.40/30` | `192.168.0.42/30` |
| `e1` | `em1` (Troncal LAN) | `SwitchAccesoS e0` (`dot1q`) | Nativa `99` + VLANs `10, 20, 30` | Subinterfaces VLAN |
| `e1` (`VLAN 10`) | `em1.10` (`ADMIN`) | `Administracion/finanzas` | `192.168.0.0/28` | `192.168.0.1/28` |
| `e1` (`VLAN 20`) | `em1.20` (`GERENCIA`) | `GerenciaGeneral` | `192.168.0.16/29` | `192.168.0.17/29` |
| `e1` (`VLAN 30`) | `em1.30` (`TI`) | `TI/Comunicaciones` | `192.168.0.24/29` | `192.168.0.25/29` |
| `e2` | `em2` (`DMZ`) | `SwitchDMZ e0` | `192.168.0.32/29` | `192.168.0.33/29` |

---

## Paso a paso en pfSense

### 1. Asignación inicial por consola (menú de texto de pfSense)
1. Seleccionar opción `1) Assign Interfaces`:
   - Crear VLANs sobre `em1`: VLAN `10`, VLAN `20`, VLAN `30`.
   - `WAN` $\rightarrow$ `em0`
   - `LAN` $\rightarrow$ `em1.30` (para administrar la WebGUI desde la VM de **TI/Comunicaciones**)
   - `OPT1` $\rightarrow$ `em1.10` (Administración y Finanzas)
   - `OPT2` $\rightarrow$ `em1.20` (Gerencia General)
   - `OPT3` $\rightarrow$ `em2` (DMZ)
2. Seleccionar opción `2) Set interface(s) IP address` y asignar las IPs de la tabla superior (**desactivando** el servidor DHCP local de pfSense, ya que el DHCP corporativo será `DNSDHCP` en `192.168.0.34`).

### 2. Ajustes críticos de enrutamiento interno (WebGUI desde `TI` en `https://192.168.0.25`)
1. **Desactivar bloqueo de redes privadas en WAN (`Interfaces -> WAN`):**
   - Desmarcar **Block private networks and loopback addresses** y **Block bogon networks** (porque `192.168.0.40/30` y `10.0.0.0/8` son redes privadas corporativas).
2. **Desactivar NAT saliente (`Firewall -> NAT -> Outbound`):**
   - Cambiar a **Disable Outbound NAT rule generation** para que pfSense enrute de forma transparente entre Casa Matriz, DMZ y Sucursal sin ocultar las IPs reales de las VLANs (necesario para que las ACLs y el DHCP Relay funcionen con las IPs reales de cada departamento).
3. **Gateway y Rutas Estáticas (`System -> Routing`):**
   - Crear Gateway `GW_SANTIAGO` en interfaz `WAN` con IP `192.168.0.41` y marcarlo como *Default Gateway* (o agregar rutas estáticas hacia `10.0.0.0/28`, `10.0.0.16/28`, `10.0.0.32/28`, `10.10.10.0/30` y `10.10.10.4/30` vía `192.168.0.41`).

### 3. Configurar DHCP Relay (`Services -> DHCP Relay`)
- Marcar **Enable DHCP relay on interface**.
- Seleccionar las interfaces de clientes de Casa Matriz: `LAN (TI)`, `ADMIN (VLAN 10)`, `GERENCIA (VLAN 20)`.
- En **Destination server**, ingresar `192.168.0.34` (`DNSDHCP`).

### 4. Reglas de Firewall / ACLs en pfSense (`Firewall -> Rules`)
- **En `WAN` (tráfico entrante desde Sucursal Valparaíso):**
  - Permitir UDP `67-68` hacia `192.168.0.34` (para que lleguen los paquetes DHCP Relay desde `Valparaiso`).
  - Permitir TCP/UDP `53` hacia `192.168.0.34` (DNS).
  - Permitir TCP `80, 443` hacia `192.168.0.36` (`HTTPS`).
  - Permitir tráfico entre departamentos autorizados (ej. `Ventas` $\leftrightarrow$ `Administracion`, `TI` $\rightarrow$ `any`).
- **En `TI (VLAN 30)`:** Permitir todo (`any -> any`) para administración y pruebas.
- **En `GERENCIA (VLAN 20)` y `ADMIN (VLAN 10)`:**
  - Permitir DNS (`192.168.0.34`), HTTP/HTTPS (`192.168.0.36`) y comunicación inter-departamental según política; bloquear acceso administrativo a la WebGUI de pfSense desde `ADMIN` (TCP 443/80 hacia `This Firewall`) como restricción adicional de seguridad.
- **En `DMZ`:** Permitir respuestas hacia las redes internas, bloqueando inicio de conexiones no solicitadas desde DMZ hacia `GERENCIA`.
