# Guion de Demostración Operativa en Clases (15 Minutos)

Según la rúbrica oficial (60% grupal + 40% individual), la exposición dura **15 minutos** y cualquier integrante puede ser elegido por el docente para ejecutar pruebas o cambios en vivo.

---

## Etapa 1: Arquitectura y Decisiones (5 min)

1. **Problema resuelto:** Red plana anterior sufría congestión por transferencias pesadas desde Soporte hacia Ventas/Administración y carecía de control de acceso y tolerancia a fallos WAN.
2. **Diseño implementado:**
   - **Casa Matriz (Santiago):** Segmentada con `FirewallSantiago` (pfSense) en VLAN 10 (Admin), VLAN 20 (Gerencia), VLAN 30 (TI) y una **DMZ** aislada (`192.168.0.32/29`) con `DNSDHCP` (`.34`), `ACDC` (`.35`) y `HTTPS` (`.36`).
   - **Sucursal (Valparaíso):** Segmentada con trunk 802.1Q hacia `Valparaiso` (`c2691`) en VLAN 10 (Ventas), VLAN 20 (Soporte) y VLAN 30 (Bodega), usando `ip helper-address 192.168.0.34` para DHCP centralizado.
   - **Variante 9 (Redundancia de Enrutamiento):** Dos enlaces punto a punto Capa 3 entre sedes (`10.10.10.0/30` principal con `AD = 1` y `10.10.10.4/30` respaldo con `AD = 10`).

---

## Etapa 2: Operación Integrada y Variante 9 (10 min)

### Prueba 1 — DHCP Relay, DNS y Acceso HTTP (Positiva)
En la VM de **Ventas** (Sucursal, VLAN 10):
```cmd
ipconfig /release && ipconfig /renew
ipconfig /all
nslookup www.technomarket.cl
```
- **Qué mostrar:** Recibe IP `10.0.0.x/28`, Gateway `10.0.0.1` y DNS `192.168.0.34` vía DHCP Relay a través de la WAN. Luego abrir `http://www.technomarket.cl` en el navegador y mostrar el portal de TechnoMarket.

### Prueba 2 — Restricciones Funcionales mediante ACL (Positiva y Negativa)
En la VM de **Soporte Técnico** (Sucursal, VLAN 20, `10.0.0.18`):
- **Flujo permitido (Positiva):**
  ```cmd
  nslookup www.technomarket.cl
  curl -I http://www.technomarket.cl
  ```
- **Flujo bloqueado (Negativa):** Intentar conectarse/hacer ping a **Ventas** (`10.0.0.2`) y a **Administración/Finanzas** (`192.168.0.2`):
  ```cmd
  ping 10.0.0.2
  ping 192.168.0.2
  ```
- **Evidencia en router `Valparaiso`:**
  ```ios
  show access-lists ACL_SOPORTE_IN
  ```
  *(Mostrar el incremento de contadores `matches` en las líneas `deny`).*

### Prueba 3 — Variante 9: Redundancia de Enrutamiento (Evidencia Central)
*(Puedes apoyarte en `python scripts/demo_variante9.py` o ejecutarlo directo en consola):*

1. **Comprobar ruta principal activa:**
   - En `Santiago`: `show ip route static` $\rightarrow$ muestra `10.0.0.0/28 [1/0] via 10.10.10.2`.
   - En `Ventas`: `tracert -d 192.168.0.36` $\rightarrow$ primer salto WAN pasa por `10.10.10.1`.
2. **Deshabilitar enlace principal y probar conmutación:**
   - En `Santiago`:
     ```ios
     configure terminal
     interface FastEthernet0/0
      shutdown
     end
     ```
   - Mostrar `show ip route static` en `Santiago` $\rightarrow$ ahora instala automáticamente las rutas flotantes **`[10/0] via 10.10.10.6`**.
   - En `Ventas`: repetir `tracert -d 192.168.0.36` (ahora salta por **`10.10.10.5`**) y recargar `http://www.technomarket.cl` demostrando continuidad operativa sin caída del servicio.
3. **Restaurar enlace principal:**
   - En `Santiago`: `conf t` $\rightarrow$ `int fa0/0` $\rightarrow$ `no shutdown`.
   - Mostrar `show ip route static` y `tracert -d 192.168.0.36` regresando a `[1/0] via 10.10.10.2` / `10.10.10.1`.

---

## Etapa 3: Posibles "Cambios Controlados" que puede pedir el Docente

Ten a mano estos 3 cambios rápidos que suelen solicitarse en evaluación en vivo:

1. **"Inviertan la preferencia para que el enlace `10.10.10.4/30` sea el principal sin apagar `Fa0/0`":**
   - En `Santiago`: cambiar las rutas de `10.10.10.2` a distancia `20` (ej. `ip route 10.0.0.0 255.255.255.240 10.10.10.2 20` y eliminar la de AD 1 con `no ip route 10.0.0.0 255.255.255.240 10.10.10.2`).
   - En `Valparaiso`: `ip route 0.0.0.0 0.0.0.0 10.10.10.1 20` y `no ip route 0.0.0.0 0.0.0.0 10.10.10.1`.
2. **"Permitan temporalmente ping/tráfico desde Soporte Técnico hacia Ventas":**
   - En `Valparaiso`:
     ```ios
     ip access-list extended ACL_SOPORTE_IN
      5 permit icmp 10.0.0.16 0.0.0.15 10.0.0.0 0.0.0.15
     ```
3. **"Agreguen un alias DNS nuevo (ej. `soporte.technomarket.cl`) apuntando al servidor HTTP":**
   - En `DNSDHCP`: agregar `soporte IN CNAME www.technomarket.cl.` en `/var/named/technomarket.cl.zone`, subir el `Serial` en +1 y ejecutar `sudo rndc reload` (o `sudo systemctl reload named`).
