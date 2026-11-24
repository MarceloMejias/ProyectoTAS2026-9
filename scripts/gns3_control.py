#!/usr/bin/env python3
"""
Cliente de automatización en vivo para GNS3 + Consolas Cisco IOS (Equipo 1 — Variante 1).
- Autodetecta IP, puerto y credenciales HTTP de GNS3 leyendo %APPDATA%\\GNS3\\*\\gns3_server.ini.
- Enciende únicamente los routers (Santiago, Vina/Valparaiso) y switches Ethernet (0 MB RAM).
- Limpia cualquier segundo enlace WAN residual (Fa1/0 <-> Fa0/1) si quedó de pruebas previas.
- Sincroniza cada comando esperando el prompt real de Cisco IOS e inyecta las configs de Variante 1.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "configs" / "routers"

SANTIAGO_ID = "19d852b9-922e-4eec-ab39-248aa419245b"
VINA_ID = "4f30d82d-9494-4bb1-8abd-e751783ac5a3"
SWITCH_V_ID = "cba0b89a-696e-43c4-8b01-af8d3ed8becb"

ROUTERS = {
    "santiago": {
        "node_id": SANTIAGO_ID,
        "names": {"santiago"},
        "vlans": [],  # Santiago solo usa puertos ruteados Fa0/0 y Fa0/1 en Variante 1
        "cfg": CONFIGS_DIR / "Santiago_variante1.cfg",
    },
    "valparaiso": {
        "node_id": VINA_ID,
        "names": {"vina", "valparaiso"},
        "vlans": [(10, "VENTAS"), (20, "SOPORTE"), (30, "BODEGA"), (99, "NATIVA")],
        "cfg": CONFIGS_DIR / "Vina_variante1.cfg",
    },
}


@dataclass
class GNS3Config:
    protocol: str = "http"
    host: str = "127.0.0.1"
    port: int = 3080
    user: str = ""
    password: str = ""

    @property
    def base_url(self) -> str:
        h = "127.0.0.1" if self.host in ("0.0.0.0", "::", "") else self.host
        return f"{self.protocol}://{h}:{self.port}"


def discover_gns3_config(override_api: str | None = None) -> GNS3Config:
    cfg = GNS3Config()
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates = sorted(Path(appdata).glob("GNS3/**/gns3_server.ini"), reverse=True)
        for ini_path in candidates:
            parser = configparser.RawConfigParser()
            parser.read(ini_path, encoding="utf-8")
            if parser.has_section("Server"):
                cfg.protocol = parser.get("Server", "protocol", fallback="http").strip()
                cfg.host = parser.get("Server", "host", fallback="127.0.0.1").strip()
                cfg.port = parser.getint("Server", "port", fallback=3080)
                auth_enabled = parser.get("Server", "auth", fallback="false").strip().lower() == "true"
                if auth_enabled:
                    cfg.user = parser.get("Server", "user", fallback="").strip()
                    cfg.password = parser.get("Server", "password", fallback="").strip()
                break

    if override_api:
        m = re.match(r"^(https?)://([^:/]+):?(\d+)?", override_api.strip())
        if m:
            cfg.protocol = m.group(1)
            cfg.host = m.group(2)
            if m.group(3):
                cfg.port = int(m.group(3))
    return cfg


class GNS3Client:
    def __init__(self, cfg: GNS3Config) -> None:
        self.cfg = cfg

    def request(self, method: str, endpoint: str, payload: object | None = None) -> object:
        url = f"{self.cfg.base_url}/{endpoint.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cfg.user:
            token = base64.b64encode(f"{self.cfg.user}:{self.cfg.password}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    def get_active_project(self, project_name: str = "ProyectoTAS") -> dict:
        projects: list[dict] = self.request("GET", "/v2/projects")  # type: ignore[assignment]
        if not projects:
            raise SystemExit("No hay proyectos registrados en GNS3 Server. Abre ProyectoTAS.gns3 en GNS3 primero.")

        for p in projects:
            if p.get("status") == "opened" and p.get("name") == project_name:
                return p
        for p in projects:
            if p.get("status") == "opened":
                return p
        for p in projects:
            if p.get("name") == project_name:
                print(f"[*] Abriendo proyecto '{project_name}' vía API GNS3...")
                return self.request("POST", f"/v2/projects/{p['project_id']}/open", {})  # type: ignore[return-value]

        raise SystemExit(f"No se encontró el proyecto '{project_name}' abierto en GNS3.")

    def ensure_lightweight_stage_ready(self) -> tuple[dict, dict[str, dict]]:
        """Asegura switches y routers encendidos (sin tocar VMs de VMware) y limpia enlace extra si existía."""
        proj = self.get_active_project()
        pid = proj["project_id"]

        # Limpiar segundo enlace WAN si quedó creado de la prueba anterior
        links: list[dict] = self.request("GET", f"/v2/projects/{pid}/links")  # type: ignore[assignment]
        for lk in links:
            eps = {(e["node_id"], e["adapter_number"], e["port_number"]) for e in lk.get("nodes", [])}
            if (SANTIAGO_ID, 1, 0) in eps and (VINA_ID, 0, 1) in eps:
                print("[*] Eliminando enlace WAN secundario innecesario para Equipo 1...")
                self.request("DELETE", f"/v2/projects/{pid}/links/{lk['link_id']}")

        nodes: list[dict] = self.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        started_any_router = False
        for n in nodes:
            if n.get("node_type") in ("ethernet_switch", "dynamips") and n.get("status") != "started":
                print(f"[*] Encendiendo nodo liviano '{n['name']}' ({n['node_type']})...")
                self.request("POST", f"/v2/projects/{pid}/nodes/{n['node_id']}/start", {})
                if n.get("node_type") == "dynamips":
                    started_any_router = True

        if started_any_router:
            print("[*] Esperando 5s iniciales para descompresión de imagen Cisco IOS...")
            time.sleep(5.0)

        nodes = self.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        router_nodes: dict[str, dict] = {}
        for key, meta in ROUTERS.items():
            for n in nodes:
                if n["node_id"] == meta["node_id"] or n["name"].lower() in meta["names"]:
                    router_nodes[key] = n
                    break
        return proj, router_nodes

    def resolve_console_target(self, node: dict) -> tuple[str, int]:
        chost = (node.get("console_host") or "").strip()
        if chost in ("", "0.0.0.0", "::", "0:0:0:0:0:0:0:0"):
            chost = "127.0.0.1" if self.cfg.host in ("0.0.0.0", "::", "") else self.cfg.host
        cport = int(node["console"])
        return chost, cport


class IOSConsole:
    """Cliente sincronizado por prompt real sobre socket TCP para consolas Cisco IOS en Dynamips."""

    PROMPT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(?:\([A-Za-z0-9_-]+\))?[#>]$")

    def __init__(self, host: str, port: int, timeout: float = 8.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.25)

    def close(self) -> None:
        self.sock.close()

    def flush_input(self) -> None:
        self.sock.settimeout(0.05)
        try:
            while self.sock.recv(4096):
                pass
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(0.25)

    @classmethod
    def _extract_trailing_prompt(cls, text: str) -> str:
        if not text:
            return ""
        tail = text.replace("\r", "\n").split("\n")[-1].strip()
        return tail if cls.PROMPT_RE.match(tail) else ""

    def send(self, cmd: str, timeout: float = 20.0) -> str:
        """Envía un comando y espera hasta recibir el siguiente prompt válido de IOS."""
        self.flush_input()
        self.sock.sendall((cmd + "\r\n").encode("ascii"))
        deadline = time.time() + timeout
        buf = ""
        saw_newline = cmd == ""

        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                decoded = chunk.decode("latin-1", errors="ignore")
                buf += decoded
                if "\n" in decoded or "\r" in decoded:
                    saw_newline = True
                if saw_newline and self._extract_trailing_prompt(buf):
                    break
            except socket.timeout:
                if saw_newline and self._extract_trailing_prompt(buf):
                    break
        return buf

    def ensure_priv_exec(self, wait_boot_seconds: float = 90.0) -> str:
        deadline = time.time() + wait_boot_seconds
        prompt = ""
        while time.time() < deadline:
            out = self.send("", timeout=2.5)
            if "initial configuration dialog" in out.lower():
                out = self.send("no", timeout=5.0)
            prompt = self._extract_trailing_prompt(out)
            if prompt:
                break
            time.sleep(1.0)

        if not prompt:
            raise RuntimeError("Tiempo de espera agotado esperando prompt de Cisco IOS.")

        for _ in range(6):
            if "(vlan)" in prompt.lower():
                out = self.send("abort", timeout=5.0)
            elif "(" in prompt and prompt.endswith("#"):
                out = self.send("end", timeout=5.0)
            elif prompt.endswith(">"):
                out = self.send("enable", timeout=5.0)
            else:
                break
            prompt = self._extract_trailing_prompt(out) or self._extract_trailing_prompt(self.send("", timeout=3.0))

        self.send("terminal length 0", timeout=5.0)
        return prompt

    def initialize_flash_for_vlans(self) -> None:
        print("  [*] Inicializando flash: del router c2691 (erase flash:, tarda ~40s en Dynamips)...", end="", flush=True)
        self.ensure_priv_exec()
        self.flush_input()
        self.sock.sendall(b"erase flash:\r\n")

        deadline = time.time() + 120.0
        buf = ""
        confirmed = False
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if chunk:
                    text = chunk.decode("latin-1", errors="ignore")
                    buf += text
                    if "e" in text:
                        sys.stdout.write(".")
                        sys.stdout.flush()
                    if not confirmed and ("confirm" in buf.lower() or "[" in buf):
                        self.sock.sendall(b"\r\n")
                        confirmed = True
                    if ("complete" in buf.lower() or "erased" in buf.lower()) and self._extract_trailing_prompt(buf):
                        break
            except socket.timeout:
                if confirmed and ("complete" in buf.lower() or "erased" in buf.lower()):
                    if self._extract_trailing_prompt(buf) or self._extract_trailing_prompt(self.send("", timeout=2.0)):
                        break
        print(" [OK]")
        self.ensure_priv_exec()

    def configure_vlans(self, vlans: list[tuple[int, str]]) -> None:
        if not vlans:
            return
        self.ensure_priv_exec()
        current_vlans = self.send("show vlan-switch brief", timeout=8.0)
        missing = [vid for vid, _ in vlans if not re.search(rf"^\s*{vid}\s+", current_vlans, re.MULTILINE)]
        if not missing:
            print("  [OK] VLANs ya existen en vlan.dat.")
            return

        for attempt in range(2):
            self.ensure_priv_exec()
            out = self.send("vlan database", timeout=5.0)
            if "(vlan)" not in out.lower():
                raise RuntimeError(f"No se pudo entrar a 'vlan database':\n{out}")

            for vid, vname in vlans:
                self.send(f"vlan {vid} name {vname}", timeout=5.0)

            exit_out = self.send("exit", timeout=10.0)
            prompt = self._extract_trailing_prompt(exit_out) or self._extract_trailing_prompt(self.send("", timeout=3.0))

            failed = (
                "(vlan)" in prompt.lower()
                or "nv storage failure" in exit_out.lower()
                or "not enough space" in exit_out.lower()
                or "error on database apply" in exit_out.lower()
            )
            if not failed:
                return

            self.send("abort", timeout=5.0)
            if attempt == 0:
                self.initialize_flash_for_vlans()
            else:
                raise RuntimeError(f"No fue posible guardar vlan.dat tras inicializar flash:\n{exit_out}")


def cmd_status(client: GNS3Client) -> None:
    try:
        projects: list[dict] = client.request("GET", "/v2/projects")  # type: ignore[assignment]
    except urllib.error.URLError as exc:
        raise SystemExit(f"No se pudo conectar a GNS3 Server en {client.cfg.base_url}: {exc}")

    print(f"=== GNS3 Server conectado en {client.cfg.base_url} ===")
    for p in projects:
        print(f"- Proyecto: {p['name']} [{p['status']}] id={p['project_id']}")
        if p["status"] == "opened":
            nodes: list[dict] = client.request("GET", f"/v2/projects/{p['project_id']}/nodes")  # type: ignore[assignment]
            for n in nodes:
                print(
                    f"    * {n['name']:24s} type={n['node_type']:15s} "
                    f"status={n['status']:8s} console={n.get('console_host')}:{n.get('console')}"
                )


def push_router_config(client: GNS3Client, router_key: str, node: dict) -> None:
    info = ROUTERS[router_key]
    cfg_path: Path = info["cfg"]  # type: ignore[assignment]
    vlans: list[tuple[int, str]] = info["vlans"]  # type: ignore[assignment]
    host, port = client.resolve_console_target(node)

    print(f"\n[*] Conectando a {node['name']} ({host}:{port})...")
    con = IOSConsole(host, port)
    try:
        con.ensure_priv_exec()

        if vlans:
            print(f"[*] Configurando VLANs en NM-16ESW: {vlans}...")
            con.configure_vlans(vlans)
            con.ensure_priv_exec()

        print(f"[*] Aplicando {cfg_path.name}...")
        cfg_out = con.send("configure terminal", timeout=5.0)
        prompt = con._extract_trailing_prompt(cfg_out)
        if "(config)" not in prompt.lower():
            raise RuntimeError(f"No se pudo entrar a 'configure terminal'. Prompt='{prompt}', Salida:\n{cfg_out}")

        for raw_line in cfg_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("!") or line.startswith("version ") or line == "end":
                continue
            resp = con.send(raw_line.rstrip(), timeout=5.0)
            if "% Invalid input" in resp:
                print(f"  [WARN] Comando rechazado '{line}':\n    {resp.strip()}")

        con.send("end", timeout=5.0)
        con.ensure_priv_exec()
        print("[*] Guardando configuración en NVRAM (write memory)...")
        con.send("write memory", timeout=15.0)
        print(f"[OK] Configuración aplicada y guardada exitosamente en {router_key}.")
    finally:
        con.close()


def cmd_routes(client: GNS3Client) -> None:
    _, router_nodes = client.ensure_lightweight_stage_ready()
    for key, node in router_nodes.items():
        host, port = client.resolve_console_target(node)
        print(f"\n================ {key.upper()} ({host}:{port}) ================")
        con = IOSConsole(host, port)
        try:
            con.ensure_priv_exec()
            print(con.send("show ip interface brief | exclude unassigned", timeout=8.0))
            print(con.send("show ip route", timeout=8.0))
        finally:
            con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Control inteligente de GNS3 y routers Cisco IOS (Equipo 1)")
    parser.add_argument("--api", default=None, help="URL opcional de GNS3 Server API (autodetectada por defecto)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Consulta proyectos y nodos en GNS3 API")
    p_push = sub.add_parser("push-configs", help="Enciende routers/switches livianos e inyecta configs Variante 1")
    p_push.add_argument("--router", choices=["all", "santiago", "valparaiso"], default="all")
    sub.add_parser("routes", help="Muestra interfaces activas y tablas de enrutamiento de ambos routers")

    args = parser.parse_args()
    cfg = discover_gns3_config(args.api)
    client = GNS3Client(cfg)

    if args.cmd == "status":
        cmd_status(client)
    elif args.cmd == "push-configs":
        _, router_nodes = client.ensure_lightweight_stage_ready()
        targets = ["santiago", "valparaiso"] if args.router == "all" else [args.router]
        for t in targets:
            if t not in router_nodes:
                raise SystemExit(f"No se encontró el router '{t}' en la topología activa.")
            push_router_config(client, t, router_nodes[t])
    elif args.cmd == "routes":
        cmd_routes(client)


if __name__ == "__main__":
    main()
