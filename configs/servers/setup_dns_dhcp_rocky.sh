#!/usr/bin/env bash
# =============================================================================
# Configuración automatizada de Servidor DNSDHCP (Rocky Linux - RockyTAS)
# IP Estática en DMZ: 192.168.0.34/29 | Gateway: 192.168.0.33
# Servicios: BIND9 (DNS interno) + Kea DHCP4 / ISC DHCP (Ámbitos + Relay)
# =============================================================================
set -euo pipefail

IFACE="${1:-$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="ethernet"{print $1; exit}')}"
CONN_NAME="$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v dev="$IFACE" '$2==dev{print $1; exit}')"

echo "[1/5] Configurando IP estática 192.168.0.34/29 en $IFACE ($CONN_NAME)..."
nmcli connection modify "$CONN_NAME" \
  ipv4.method manual \
  ipv4.addresses "192.168.0.34/29" \
  ipv4.gateway "192.168.0.33" \
  ipv4.dns "127.0.0.1" \
  connection.autoconnect yes
nmcli connection up "$CONN_NAME"

echo "[2/5] Verificando/instalando paquetes bind y dhcp-server (o kea)..."
if ! rpm -q bind >/dev/null 2>&1; then
  dnf install -y bind bind-utils
fi
if ! rpm -q dhcp-server >/dev/null 2>&1 && ! rpm -q kea >/dev/null 2>&1; then
  dnf install -y dhcp-server || dnf install -y kea
fi

echo "[3/5] Configurando DNS interno (BIND - technomarket.cl)..."
cat >/etc/named.conf <<'EOF'
options {
    listen-on port 53 { 127.0.0.1; 192.168.0.34; };
    directory   "/var/named";
    allow-query { 127.0.0.1; 192.168.0.0/24; 10.0.0.0/8; 10.10.10.0/24; };
    recursion yes;
    dnssec-validation no;
};

zone "technomarket.cl" IN {
    type master;
    file "technomarket.cl.zone";
    allow-update { none; };
};

zone "0.168.192.in-addr.arpa" IN {
    type master;
    file "192.168.0.rev";
    allow-update { none; };
};
EOF

cat >/var/named/technomarket.cl.zone <<'EOF'
$TTL 86400
@   IN  SOA ns1.technomarket.cl. admin.technomarket.cl. (
        2026112301 ; Serial
        3600       ; Refresh
        1800       ; Retry
        604800     ; Expire
        86400 )    ; Minimum TTL
;
@       IN  NS      ns1.technomarket.cl.
ns1     IN  A       192.168.0.34
dns     IN  CNAME   ns1.technomarket.cl.
acdc    IN  A       192.168.0.35
www     IN  A       192.168.0.36
portal  IN  CNAME   www.technomarket.cl.
intranet IN CNAME   www.technomarket.cl.
EOF

cat >/var/named/192.168.0.rev <<'EOF'
$TTL 86400
@   IN  SOA ns1.technomarket.cl. admin.technomarket.cl. (
        2026112301 ; Serial
        3600       ; Refresh
        1800       ; Retry
        604800     ; Expire
        86400 )    ; Minimum TTL
;
@   IN  NS  ns1.technomarket.cl.
34  IN  PTR ns1.technomarket.cl.
35  IN  PTR acdc.technomarket.cl.
36  IN  PTR www.technomarket.cl.
EOF

chown root:named /var/named/technomarket.cl.zone /var/named/192.168.0.rev
chmod 640 /var/named/technomarket.cl.zone /var/named/192.168.0.rev
named-checkconf
named-checkzone technomarket.cl /var/named/technomarket.cl.zone
systemctl enable --now named

echo "[4/5] Configurando DHCP con ámbitos diferenciados para Casa Matriz y Sucursal..."
if rpm -q dhcp-server >/dev/null 2>&1; then
  cat >/etc/dhcp/dhcpd.conf <<'EOF'
authoritative;
default-lease-time 3600;
max-lease-time 7200;
option domain-name "technomarket.cl";
option domain-name-servers 192.168.0.34;

# Subred local DMZ (sin pool dinámico, requerida para levantar el servicio en la interfaz)
subnet 192.168.0.32 netmask 255.255.255.248 {
}

# --- CASA MATRIZ (SANTIAGO) ---
# VLAN 10: Administración y Finanzas (8 empleados)
subnet 192.168.0.0 netmask 255.255.255.240 {
    range 192.168.0.2 192.168.0.14;
    option routers 192.168.0.1;
}

# VLAN 20: Gerencia General (3 empleados)
subnet 192.168.0.16 netmask 255.255.255.248 {
    range 192.168.0.18 192.168.0.22;
    option routers 192.168.0.17;
}

# VLAN 30: TI y Comunicaciones (4 empleados)
subnet 192.168.0.24 netmask 255.255.255.248 {
    range 192.168.0.26 192.168.0.30;
    option routers 192.168.0.25;
}

# --- SUCURSAL (VALPARAÍSO) - Atendidas vía DHCP Relay ---
# VLAN 10: Ventas (12 empleados)
subnet 10.0.0.0 netmask 255.255.255.240 {
    range 10.0.0.2 10.0.0.14;
    option routers 10.0.0.1;
}

# VLAN 20: Soporte Técnico (10 empleados)
subnet 10.0.0.16 netmask 255.255.255.240 {
    range 10.0.0.18 10.0.0.30;
    option routers 10.0.0.17;
}

# VLAN 30: Bodega y Logística (6 empleados)
subnet 10.0.0.32 netmask 255.255.255.240 {
    range 10.0.0.34 10.0.0.46;
    option routers 10.0.0.33;
}
EOF
  systemctl enable --now dhcpd
else
  cat >/etc/kea/kea-dhcp4.conf <<EOF
{
  "Dhcp4": {
    "interfaces-config": { "interfaces": [ "$IFACE" ], "dhcp-socket-type": "udp" },
    "valid-lifetime": 3600,
    "option-data": [
      { "name": "domain-name-servers", "data": "192.168.0.34" },
      { "name": "domain-search", "data": "technomarket.cl" }
    ],
    "subnet4": [
      { "id": 1, "subnet": "192.168.0.32/29" },
      { "id": 10, "subnet": "192.168.0.0/28",  "pools": [{ "pool": "192.168.0.2 - 192.168.0.14" }],  "option-data": [{ "name": "routers", "data": "192.168.0.1" }] },
      { "id": 20, "subnet": "192.168.0.16/29", "pools": [{ "pool": "192.168.0.18 - 192.168.0.22" }], "option-data": [{ "name": "routers", "data": "192.168.0.17" }] },
      { "id": 30, "subnet": "192.168.0.24/29", "pools": [{ "pool": "192.168.0.26 - 192.168.0.30" }], "option-data": [{ "name": "routers", "data": "192.168.0.25" }] },
      { "id": 40, "subnet": "10.0.0.0/28",     "pools": [{ "pool": "10.0.0.2 - 10.0.0.14" }],         "option-data": [{ "name": "routers", "data": "10.0.0.1" }] },
      { "id": 50, "subnet": "10.0.0.16/28",    "pools": [{ "pool": "10.0.0.18 - 10.0.0.30" }],        "option-data": [{ "name": "routers", "data": "10.0.0.17" }] },
      { "id": 60, "subnet": "10.0.0.32/28",    "pools": [{ "pool": "10.0.0.34 - 10.0.0.46" }],        "option-data": [{ "name": "routers", "data": "10.0.0.33" }] }
    ]
  }
}
EOF
  systemctl enable --now kea-dhcp4
fi

echo "[5/5] Abriendo puertos DNS y DHCP en firewalld..."
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-service=dns
  firewall-cmd --permanent --add-service=dhcp
  firewall-cmd --reload
fi

echo "Listo. Verifica con: dig @127.0.0.1 www.technomarket.cl +short"
