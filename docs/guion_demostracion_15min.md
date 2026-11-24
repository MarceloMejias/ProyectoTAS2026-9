# Guion de Demostración Operativa en Clases (15 Minutos — Equipo 1)

Según la rúbrica oficial (60% grupal + 40% individual), la presentación dura **15 minutos** y cualquier integrante puede ser elegido para ejecutar pruebas y un cambio controlado en vivo.

---

## Etapa 1: Arquitectura y Decisiones (5 min)

1. **Problema resuelto:** La red plana original carecía de segmentación, control de tráfico entre Soporte y Ventas/Administración, y gestión centralizada de direccionamiento IP.
2. **Diseño implementado:**
   - **Casa Matriz (Santiago):** Segmentada mediante `FirewallSantiago` (pfSense) en VLAN 10 (Admin), VLAN 20 (Gerencia), VLAN 30 (TI) y una **DMZ** (`192.168.0.32/29`) que aloja el servidor **`DNSDHCP` centralizado (`192.168.0.34`)** y el servidor web **`HTTPS` (`192.168.0.36`)**.
   - **Sucursal (Valparaíso):** Segmentada con trunk 802.1Q hacia el router `Valparaiso` (`c2691`) en VLAN 10 (Ventas), VLAN 20 (Soporte) y VLAN 30 (Bodega).
   - **Variante 1 (DHCP Centralizado entre Sedes):** Ninguna sede tiene DHCP local disperso; las SVIs `Vlan10`, `Vlan20` y `Vlan30` en Valparaíso usan **`ip helper-address 192.168.0.34`** (DHCP Relay) para solicitar concesiones a través del enlace WAN hacia los ámbitos diferenciados definidos en Casa Matriz.

---

## Etapa 2: Operación Integrada y Variante 1 (10 min)

### Prueba 1 — Variante 1: Concesión Remota por Relay en Dos Ámbitos + Gateway/DNS
1. **Mostrar configuración de Relay en el router `Valparaiso`:**
   ```ios
   show ip interface Vlan10 | include Internet|Helper
   show ip interface Vlan20 | include Internet|Helper
   ```
   *(Muestra `Helper address is 192.168.0.34` en ambas VLANs).*
2. **Concesión en Ámbito 1 (VLAN 10 — Ventas `10.0.0.0/28`):**
   - En la VM `Ventas` (o `VPCS-Ventas`):
     ```cmd
     ipconfig /release && ipconfig /renew
     ipconfig /all
     ```
   - **Comprobar:** IP `10.0.0.x`, Máscara `255.255.255.240`, **Gateway `10.0.0.1`**, **DNS `192.168.0.34`** y dominio `technomarket.cl`.
3. **Concesión en Ámbito 2 (VLAN 20 — Soporte Técnico `10.0.0.16/28`):**
   - En `SoporteTecnico` / `VPCS-Soporte`: ejecutar `ip dhcp` (o `ipconfig /renew`) y `show ip` (`ipconfig /all`).
   - **Comprobar:** IP `10.0.0.18+`, **Gateway `10.0.0.17`** y **DNS `192.168.0.34`**, demostrando que el servidor centralizado distingue cada VLAN remota gracias al campo `giaddr` del Relay.

### Prueba 2 — DNS Interno y Acceso HTTP Corporativo
Desde el cliente `Ventas` en Sucursal:
```cmd
nslookup www.technomarket.cl
```
- Abrir `http://www.technomarket.cl` en el navegador y mostrar la intranet de **TechnoMarket Ltda.** (`192.168.0.36`).

### Prueba 3 — Restricciones Funcionales mediante ACL (Positiva y Negativa)
Desde **Soporte Técnico** (`10.0.0.18`, VLAN 20):
- **Permitido (Positiva):** Acceso a DNS (`192.168.0.34`), DHCP y HTTP (`192.168.0.36`).
- **Denegado (Negativa):** Intentar `ping 10.0.0.2` (Ventas) y `ping 192.168.0.2` (Administración/Finanzas) $\rightarrow$ bloqueado; verificar contadores en `Valparaiso` con `show access-lists ACL_SOPORTE_IN`.

### Prueba 4 — Variante 1 (Cambio en Vivo): Modificar una Opción del Ámbito y Renovar
1. En la VM `DNSDHCP` (Casa Matriz), modificar el ámbito de `Ventas` (`10.0.0.0/28`) ejecutando el script preparado (o editando `/etc/dhcp/dhcpd.conf` / `/etc/kea/kea-dhcp4.conf`):
   ```bash
   sudo bash cambiar_opcion_ambito_dhcp.sh 192.168.0.35 sucursal.technomarket.cl
   ```
   *(Cambia el inicio del rango a `.5`, agrega `192.168.0.35` como segundo servidor DNS y cambia el dominio a `sucursal.technomarket.cl`).*
2. En el cliente de **Ventas** (Sucursal), renovar la concesión:
   ```cmd
   ipconfig /release && ipconfig /renew
   ipconfig /all
   ```
   *(O `ip dhcp` $\rightarrow$ `show ip` en `VPCS-Ventas`).*
3. **Mostrar en vivo:** El cliente ahora tiene IP `10.0.0.5`, dominio `sucursal.technomarket.cl` y servidores DNS `192.168.0.34, 192.168.0.35`.

---

## Etapa 3: Otros Posibles "Cambios Controlados" del Docente

1. **"Excluyan las primeras 8 direcciones del ámbito de Soporte (`10.0.0.16/28`) y renueven":**
   - En `DNSDHCP` (`/etc/dhcp/dhcpd.conf` o `/etc/kea/kea-dhcp4.conf`), cambiar `range 10.0.0.18 10.0.0.30;` a `range 10.0.0.25 10.0.0.30;`, reiniciar `dhcpd`/`kea-dhcp4` y renovar en `Soporte` (recibirá `.25`).
2. **"Agreguen un tercer ámbito o habiliten Relay en VLAN 30 (Bodega)":**
   - Ya está preconfigurado en `Vlan30` (`10.0.0.32/28`, Gateway `10.0.0.33`): basta conectar un `VPCS` al puerto `Ethernet3` o `Ethernet6` (VLAN 30) de `SwitchAccesoV` y ejecutar `ip dhcp`.
3. **"Permitan temporalmente ping desde Soporte hacia Ventas":**
   - En `Valparaiso`: `conf t` $\rightarrow$ `ip access-list extended ACL_SOPORTE_IN` $\rightarrow$ `5 permit icmp 10.0.0.16 0.0.0.15 10.0.0.0 0.0.0.15`.
