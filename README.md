# Proyecto de Infraestructura Corporativa — TechnoMarket Ltda. (Equipo 1)

Repositorio de configuraciones, automatización y documentación técnica para el proyecto integrador de **Taller de Administración de Sistemas (2026)**, implementado sobre **GNS3 + VMware Workstation**.

- **Sedes:** Casa Matriz (Santiago) y Sucursal (Valparaíso).
- **Variante asignada — Equipo 1 (DHCP centralizado entre sedes):** Servidor DHCP centralizado en Casa Matriz (`DNSDHCP` en DMZ `192.168.0.34`), clientes en VLANs de la Sucursal atendidos mediante **DHCP Relay** (`ip helper-address 192.168.0.34`) con múltiples ámbitos diferenciados y modificación de opciones en vivo.

---

## Estructura del Repositorio

```text
.
├── Actividad_1_TechnoMarket_Final.pdf   # Enunciado oficial y rúbrica de evaluación
├── pyproject.toml                       # Proyecto Python gestionado con uv (.venv)
├── images/                              # Imágenes Cisco IOS (c2691, c7200) e ISO pfSense (ignoradas en Git)
├── vmware/                              # Plantillas OVF reparadas y VMs listas para VMware
│   ├── pfSense/                         # VM FirewallSantiago lista con 3 NICs e1000 e ISO montada
│   ├── PC1-WIN/                         # Cliente Windows departamental
│   ├── RockyTAS/                        # Base Rocky Linux (DNSDHCP y HTTPS)
│   └── WIN-Server/                      # Servidor Windows (ACDC)
├── configs/
│   ├── routers/
│   │   ├── base/                        # Configs originales extraídas de ProyectoTAS
│   │   ├── Santiago_variante1.cfg       # Config completa Router Casa Matriz (Equipo 1)
│   │   └── Vina_variante1.cfg           # Config completa Router Sucursal (VLANs, DHCP Relay, ACLs)
│   ├── firewall/
│   │   └── pfsense_guia_config.md       # Configuración de FirewallSantiago (VLANs, DMZ, Relay, Reglas)
│   └── servers/
│       ├── setup_dns_dhcp_rocky.sh      # Automatización BIND9 DNS + DHCP Server multi-ámbito (DMZ .34)
│       ├── cambiar_opcion_ambito_dhcp.sh# Cambio rápido en vivo de opción de ámbito DHCP (Evidencia Equipo 1)
│       └── setup_https_rocky.sh         # Automatización Portal Web Corporativo HTTP (DMZ .36)
├── scripts/
│   ├── install_gns3_images.ps1          # Copia las imágenes IOS de ./images al proyecto y a GNS3 global
│   ├── create_pfsense_vm.ps1            # Genera vmware/pfSense/FirewallSantiago.vmx desde la ISO de pfSense
│   ├── enable_ssh_tailscale.ps1         # Habilita SSH entrante seguro sobre Tailscale (100.64.0.0/10)
│   ├── fix_gns3_paths.py                # Utilidad offline: inspeccionar GNS3 y corregir rutas VMX de Linux
│   ├── gns3_control.py                  # Control en vivo: autodetecta GNS3 API e inyecta configs por consola
│   └── demo_variante1.py                # Demostración automatizada Equipo 1 con clientes VPCS livianos
└── docs/
    ├── arquitectura_y_vlsm.md           # Diagrama de topología, ámbitos DHCP, tabla VLSM y seguridad
    ├── guia_instalacion_gns3_vmware.md  # Paso a paso para levantar OVFs, vmrun, imágenes y pruebas sin quemar RAM
    └── guion_demostracion_15min.md      # Guion cronometrado de pruebas para Equipo 1 y cambios en vivo
```

---

## Uso Rápido de Scripts (con `uv`)

```powershell
# 1. Ver estado de nodos y puertos detectados en GNS3
uv run python scripts/gns3_control.py status

# 2. Encender solo routers/switches livianos e inyectar configuraciones de Equipo 1
uv run python scripts/gns3_control.py push-configs

# 3A. Probar TODA la Variante 1 ahora mismo SIN encender ninguna VM (usa 2 VPCS + simulación en Santiago)
uv run python scripts/demo_variante1.py --simular-servidor --auto

# 3B. Probar la Variante 1 contra el servidor real DNSDHCP (Rocky Linux) y FirewallSantiago encendidos
uv run python scripts/demo_variante1.py
```
