#!/usr/bin/env bash
# =============================================================================
# Configuración automatizada de Servidor Web Corporativo (Rocky Linux - RockyTAS)
# IP Estática en DMZ: 192.168.0.36/29 | Gateway: 192.168.0.33 | DNS: 192.168.0.34
# Dominio: www.technomarket.cl / portal.technomarket.cl
# =============================================================================
set -euo pipefail

IFACE="${1:-$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="ethernet"{print $1; exit}')}"
CONN_NAME="$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v dev="$IFACE" '$2==dev{print $1; exit}')"

echo "[1/4] Configurando IP estática 192.168.0.36/29 en $IFACE ($CONN_NAME)..."
nmcli connection modify "$CONN_NAME" \
  ipv4.method manual \
  ipv4.addresses "192.168.0.36/29" \
  ipv4.gateway "192.168.0.33" \
  ipv4.dns "192.168.0.34" \
  connection.autoconnect yes
nmcli connection up "$CONN_NAME"

echo "[2/4] Verificando/instalando servidor web (nginx o httpd)..."
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

echo "[3/4] Publicando portal corporativo TechnoMarket Ltda. en $DOCROOT..."
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
      <li><strong>Equipo 9:</strong> Redundancia de enrutamiento de Capa 3 activa</li>
    </ul>
  </div>
</body>
</html>
EOF

systemctl enable --now "$WEB_SVC"

echo "[4/4] Abriendo puertos HTTP/HTTPS en firewalld..."
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --reload
fi

echo "Listo. Prueba local: curl -I http://192.168.0.36"
