#!/usr/bin/env python3
"""
Cliente de automatización en vivo para GNS3 + Consolas Cisco IOS (sin dependencias externas).
Permite consultar el estado del servidor GNS3, inyectar configuraciones a Santiago/Valparaíso
por consola TCP (Telnet) y consultar tablas de enrutamiento.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "configs" / "routers"

ROUTERS = {
    "santiago": {
        "port": 5000,
        "vlans": [(90, "WAN_BACKUP")],
        "cfg": CONFIGS_DIR / "Santiago_variante9.cfg",
    },
    "valparaiso": {
        "port": 5001,
        "vlans": [(10, "VENTAS"), (20, "SOPORTE"), (30, "BODEGA"), (99, "NATIVA")],
        "cfg": CONFIGS_DIR / "Vina_variante9.cfg",
    },
}


class IOSConsole:
    """Cliente ligero sobre socket TCP para consolas Dynamips en GNS3."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.4)

    def close(self) -> None:
        self.sock.close()

    def _drain(self, pause: float = 0.3) -> str:
        time.sleep(pause)
        chunks: list[bytes] = []
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
            except socket.timeout:
                break
        return b"".join(chunks).decode("latin-1", errors="ignore")

    def send(self, cmd: str, pause: float = 0.35) -> str:
        self.sock.sendall((cmd + "\r\n").encode("ascii"))
        return self._drain(pause=pause)

    def ensure_priv_exec(self) -> None:
        self.send("", pause=0.4)
        out = self.send("end", pause=0.3)
        if ">" in out:
            self.send("enable", pause=0.3)
        self.send("terminal length 0", pause=0.3)


def gns3_api_get(base_url: str, endpoint: str) -> object:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_status(api_url: str) -> None:
    try:
        projects = gns3_api_get(api_url, "/v2/projects")
    except urllib.error.URLError as exc:
        raise SystemExit(f"No se pudo conectar a GNS3 API en {api_url}: {exc}")

    print("=== Proyectos en GNS3 Server ===")
    for p in projects:  # type: ignore[union-attr]
        print(f"- {p['name']} [{p['status']}] id={p['project_id']}")
        if p["status"] == "opened":
            nodes = gns3_api_get(api_url, f"/v2/projects/{p['project_id']}/nodes")
            for n in nodes:  # type: ignore[union-attr]
                print(f"    * {n['name']:24s} status={n['status']:8s} console={n.get('console')}")


def push_router_config(host: str, router_key: str) -> None:
    info = ROUTERS[router_key]
    cfg_path: Path = info["cfg"]  # type: ignore[assignment]
    port: int = info["port"]  # type: ignore[assignment]
    vlans: list[tuple[int, str]] = info["vlans"]  # type: ignore[assignment]

    print(f"\n[*] Conectando a {router_key} ({host}:{port})...")
    con = IOSConsole(host, port)
    try:
        con.ensure_priv_exec()

        print(f"[*] Creando VLANs en vlan database: {vlans}...")
        con.send("vlan database", pause=0.4)
        for vid, vname in vlans:
            con.send(f"vlan {vid} name {vname}", pause=0.3)
        con.send("exit", pause=0.6)

        print(f"[*] Aplicando {cfg_path.name}...")
        con.send("configure terminal", pause=0.4)
        for raw_line in cfg_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("!") or line.startswith("version ") or line == "end":
                continue
            con.send(raw_line.rstrip(), pause=0.12)
        con.send("end", pause=0.4)
        con.send("write memory", pause=1.2)
        print(f"[OK] Configuración aplicada y guardada en {router_key}.")
    finally:
        con.close()


def cmd_routes(host: str) -> None:
    for name, info in ROUTERS.items():
        port = int(info["port"])  # type: ignore[arg-type]
        print(f"\n================ {name.upper()} (localhost:{port}) ================")
        con = IOSConsole(host, port)
        try:
            con.ensure_priv_exec()
            print(con.send("show ip interface brief", pause=0.5))
            print(con.send("show ip route", pause=0.6))
        finally:
            con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Control en vivo de GNS3 y routers Cisco IOS")
    parser.add_argument("--api", default="http://127.0.0.1:3080", help="URL de GNS3 Server API")
    parser.add_argument("--host", default="127.0.0.1", help="Host de consolas Telnet de GNS3")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Consulta proyectos y nodos abiertos en GNS3 API")
    p_push = sub.add_parser("push-configs", help="Inyecta las configuraciones Variante 9 por consola")
    p_push.add_argument("--router", choices=["all", "santiago", "valparaiso"], default="all")
    sub.add_parser("routes", help="Muestra interfaces y tablas de enrutamiento de ambos routers")

    args = parser.parse_args()
    if args.cmd == "status":
        cmd_status(args.api)
    elif args.cmd == "push-configs":
        targets = ["santiago", "valparaiso"] if args.router == "all" else [args.router]
        for t in targets:
            push_router_config(args.host, t)
    elif args.cmd == "routes":
        cmd_routes(args.host)


if __name__ == "__main__":
    main()
