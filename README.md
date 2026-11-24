# Proyecto de Infraestructura Corporativa — TechnoMarket Ltda. (Equipo 9)

Repositorio de configuraciones, automatización y documentación técnica para el proyecto integrador de **Taller de Administración de Sistemas (2026)**, implementado sobre **GNS3 + VMware Workstation**.

- **Sedes:** Casa Matriz (Santiago) y Sucursal (Valparaíso).
- **Variante asignada — Equipo 9 (Redundancia de enrutamiento):** Implementación de dos caminos de Capa 3 entre sedes (`10.10.10.0/30` principal con `AD = 1` y `10.10.10.4/30` respaldo flotante con `AD = 10`), con conmutación y restauración verificables en vivo.

---

## Estructura del Repositorio

```text
.
├── Actividad_1_TechnoMarket_Final.pdf   # Enunciado oficial y rúbrica de evaluación
├── images/                              # Imágenes Cisco IOS locales (c2691 y c7200; binarios ignorados en Git)
├── vmware/                              # Plantillas OVF reparadas y VMs listas para VMware
│   ├── pfSense/                         # VM FirewallSantiago lista con 3 NICs e1000 e ISO montada
│   ├── PC1-WIN/                         # Cliente Windows departamental
│   ├── RockyTAS/                        # Base Rocky Linux (DNSDHCP y HTTPS)
│   └── WIN-Server/                      # Servidor Windows (ACDC)
├── configs/
│   ├── routers/
│   │   ├── base/                        # Configs originales extraídas de ProyectoTAS
│   │   ├── Santiago_variante9.cfg       # Config completa Router Casa Matriz (Variante 9)
│   │   └── Vina_variante9.cfg           # Config completa Router Sucursal (VLANs, Relay, ACLs, Variante 9)
│   ├── firewall/
│   │   └── pfsense_guia_config.md       # Configuración de FirewallSantiago (VLANs, DMZ, Relay, Reglas)
│   └── servers/
│       ├── setup_dns_dhcp_rocky.sh      # Automatización BIND9 DNS + DHCP Server multi-ámbito (DMZ .34)
│       └── setup_https_rocky.sh         # Automatización Portal Web Corporativo HTTP (DMZ .36)
├── scripts/
│   ├── install_gns3_images.ps1          # Copia las imágenes IOS de ./images al proyecto y a GNS3 global
│   ├── create_pfsense_vm.ps1            # Genera vmware/pfSense/FirewallSantiago.vmx desde la ISO de pfSense
│   ├── fix_gns3_paths.py                # Utilidad offline: inspeccionar GNS3, cambiar IOS c2691 y crear 2do enlace WAN
│   ├── gns3_control.py                  # Control en vivo: estado GNS3 API, inyección de configs por Telnet y rutas
│   └── demo_variante9.py                # Demostración guiada/automática de falla y restauración WAN (Variante 9)
└── docs/
    ├── arquitectura_y_vlsm.md           # Diagrama de topología, tabla VLSM, seguridad y escalabilidad
    ├── guia_instalacion_gns3_vmware.md  # Paso a paso para levantar OVFs, imagen IOS y topología en Windows
    └── guion_demostracion_15min.md      # Guion cronometrado de pruebas para la presentación y cambios en vivo
```

*(Los discos virtuales pesados `*.vmdk`, imágenes `*.image`/`*.iso`, archivos `*.tar.gz` y el directorio de ejecución `gns3/ProyectoTAS/` están excluidos en `.gitignore`).*

---

## Uso Rápido de Scripts

Todos los scripts en `scripts/` usan únicamente la librería estándar de Python 3 (sin requerir `pip install`):

```powershell
# 1. Inspeccionar nodos y enlaces actuales del proyecto GNS3
python scripts/fix_gns3_paths.py inspect

# 2. Agregar el segundo enlace WAN de respaldo (Variante 9) al archivo .gns3 (con GNS3 cerrado)
python scripts/fix_gns3_paths.py add-backup-link

# 3. Con GNS3 abierto y los routers encendidos, inyectar las configuraciones completas
python scripts/gns3_control.py push-configs

# 4. Verificar interfaces y tablas de enrutamiento de ambos routers
python scripts/gns3_control.py routes

# 5. Ejecutar prueba interactiva de conmutación y restauración (Variante 9)
python scripts/demo_variante9.py
```
