#!/usr/bin/env bash
# =============================================================================
# Script para la Evidencia en Vivo de Equipo 1 (Variante 1):
# "Cambiar una opción del ámbito y renovar"
#
# Uso en la VM DNSDHCP (Rocky Linux):
#   sudo bash cambiar_opcion_ambito_dhcp.sh <nuevo_dns_secundario_o_dominio>
# Ejemplo:
#   sudo bash cambiar_opcion_ambito_dhcp.sh 192.168.0.35
# =============================================================================
set -euo pipefail

EXTRA_DNS="${1:-192.168.0.35}"
NEW_DOMAIN="${2:-sucursal.technomarket.cl}"

if [[ -f /etc/dhcp/dhcpd.conf ]]; then
  echo "[*] Actualizando opciones del Ámbito Ventas (10.0.0.0/28) en /etc/dhcp/dhcpd.conf..."
  cp /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf.bak

  # Reemplazar el bloque del ámbito Ventas (10.0.0.0/28) con las nuevas opciones
  python3 - "$EXTRA_DNS" "$NEW_DOMAIN" <<'PY'
import re, sys
extra_dns, new_domain = sys.argv[1], sys.argv[2]
path = "/etc/dhcp/dhcpd.conf"
txt = open(path, encoding="utf-8").read()
new_block = f"""subnet 10.0.0.0 netmask 255.255.255.240 {{
    range 10.0.0.5 10.0.0.14;
    option routers 10.0.0.1;
    option domain-name "{new_domain}";
    option domain-name-servers 192.168.0.34, {extra_dns};
}}"""
txt = re.sub(r"subnet\s+10\.0\.0\.0\s+netmask\s+255\.255\.255\.240\s*\{[^}]*\}", new_block, txt)
open(path, "w", encoding="utf-8").write(txt)
PY
  systemctl restart dhcpd
  echo "[OK] Servicio dhcpd reiniciado. Nuevas opciones del ámbito 10.0.0.0/28:"
  echo "     - Rango: 10.0.0.5 - 10.0.0.14"
  echo "     - Dominio: $NEW_DOMAIN"
  echo "     - Servidores DNS: 192.168.0.34, $EXTRA_DNS"
elif [[ -f /etc/kea/kea-dhcp4.conf ]]; then
  echo "[*] Actualizando opciones del Ámbito Ventas (id 40: 10.0.0.0/28) en /etc/kea/kea-dhcp4.conf..."
  cp /etc/kea/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf.bak
  python3 - "$EXTRA_DNS" "$NEW_DOMAIN" <<'PY'
import json, sys
extra_dns, new_domain = sys.argv[1], sys.argv[2]
path = "/etc/kea/kea-dhcp4.conf"
data = json.load(open(path, encoding="utf-8"))
for sub in data["Dhcp4"]["subnet4"]:
    if sub.get("subnet") == "10.0.0.0/28":
        sub["pools"] = [{"pool": "10.0.0.5 - 10.0.0.14"}]
        sub["option-data"] = [
            {"name": "routers", "data": "10.0.0.1"},
            {"name": "domain-name-servers", "data": f"192.168.0.34, {extra_dns}"},
            {"name": "domain-search", "data": new_domain},
        ]
json.dump(data, open(path, "w", encoding="utf-8"), indent=2)
PY
  systemctl restart kea-dhcp4
  echo "[OK] Servicio kea-dhcp4 reiniciado con DNS='192.168.0.34, $EXTRA_DNS', Dominio='$NEW_DOMAIN' y Rango 10.0.0.5-14."
else
  echo "No se encontró /etc/dhcp/dhcpd.conf ni /etc/kea/kea-dhcp4.conf." >&2
  exit 1
fi

echo "Ahora ejecuta en el cliente de Ventas: ipconfig /release && ipconfig /renew (o 'ip dhcp' en VPCS)."
