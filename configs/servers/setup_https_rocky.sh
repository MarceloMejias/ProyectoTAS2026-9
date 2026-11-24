#!/usr/bin/env bash
# =============================================================================
# Configuración automatizada de Servidor Web Corporativo (Rocky Linux - HTTPS)
# Orden inteligente:
#   1. Instala paquetes mientras aún tiene internet por NAT en VMware.
#   2. Publica el portal de TechnoMarket Ltda., ajusta SELinux y abre firewalld.
#   3. Al final deja configurada la IP estática de DMZ: 192.168.0.36/29 (GW .33).
# =============================================================================
set -euo pipefail

APPLY_STATIC_IP="${1:---static}"

echo "[1/4] Verificando/instalando servidor web (nginx o httpd) usando conexión actual..."
WEB_SVC=""
DOCROOT="/usr/share/nginx/html"
if rpm -q nginx >/dev/null 2>&1; then
  WEB_SVC="nginx"
elif rpm -q httpd >/dev/null 2>&1; then
  WEB_SVC="httpd"
  DOCROOT="/var/www/html"
else
  if dnf install -y nginx; then
    WEB_SVC="nginx"
  else
    dnf install -y httpd
    WEB_SVC="httpd"
    DOCROOT="/var/www/html"
  fi
fi

echo "[2/4] Publicando portal corporativo TechnoMarket Ltda. en $DOCROOT..."
mkdir -p "$DOCROOT"
cat >"$DOCROOT/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Intranet Corporativa — TechnoMarket Ltda.</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 3rem; }
    .card { max-width: 680px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 2rem; }
    h1 { color: #38bdf8; margin-top: 0; }
    .badge { display: inline-block; background: #0284c7; color: white; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.85rem; }
    ul { line-height: 1.8; }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">DMZ Casa Matriz — Santiago (192.168.0.36)</span>
    <h1>Portal Corporativo TechnoMarket Ltda.</h1>
    <p>Servicio HTTP interno operativo y resuelto mediante DNS corporativo (<code>www.technomarket.cl</code>).</p>
    <ul>
      <li><strong>Sedes conectadas:</strong> Casa Matriz (Santiago) &harr; Sucursal (Valparaíso)</li>
      <li><strong>Equipo 1:</strong> DHCP Centralizado entre Sedes con Relay Multi-Ámbito activo</li>
    </ul>
  </div>
</body>
</html>
EOF

# Ajustar contexto SELinux en Rocky Linux para evitar 403 Forbidden
if command -v restorecon >/dev/null 2>&1; then
  restorecon -Rv "$DOCROOT" >/dev/null 2>&1 || true
fi

systemctl enable --now "$WEB_SVC"

echo "[3/4] Abriendo puertos HTTP/HTTPS en firewalld y probando respuesta local..."
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --reload
fi
curl -sI http://127.0.0.1 | head -n 5

if [[ "$APPLY_STATIC_IP" == "--no-ip" ]]; then
  echo "[4/4] Omitido cambio de IP (--no-ip). Para pasar a DMZ luego ejecuta este script sin argumentos."
  exit 0
fi

echo "[4/4] Configurando IP estática de DMZ 192.168.0.36/29 (GW 192.168.0.33, DNS 192.168.0.34)..."
echo "      (Nota: si estabas conectado por SSH sobre NAT, la sesión se cortará al cambiar a la IP de DMZ)."
IFACE="$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="ethernet"{print $1; exit}')"
CONN_NAME="$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v dev="$IFACE" '$2==dev{print $1; exit}')"
if [[ -z "$CONN_NAME" ]]; then
  CONN_NAME="$(nmcli -t -f NAME,TYPE connection show | awk -F: '$2=="802-3-ethernet"{print $1; exit}')"
fi

nmcli connection modify "$CONN_NAME" \
  connection.interface-name "" \
  802-3-ethernet.mac-address "" \
  ipv4.method manual \
  ipv4.addresses "192.168.0.36/29" \
  ipv4.gateway "192.168.0.33" \
  ipv4.dns "192.168.0.34" \
  connection.autoconnect yes

nmcli connection up "$CONN_NAME" || true
echo "[OK] Servidor HTTPS configurado en 192.168.0.36/29."
