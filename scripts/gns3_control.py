#!/usr/bin/env python3
"""
Cliente de automatización para GNS3 + Consolas Cisco IOS (Equipo 1 — Variante 1).
- Autodetecta IP, puerto y credenciales HTTP de GNS3 leyendo %APPDATA%\\GNS3\\*\\gns3_server.ini.
- Conecta SwitchAccesoV Ethernet0 a Vina FastEthernet0/1 (Router-on-a-Stick 802.1Q nativo).
- En 'push-configs', inyecta atómicamente el startup-config directamente en NVRAM vía la API REST
  de GNS3 (sin depender de Telnet ni colisionar con ventanas Solar-PuTTY abiertas) y arranca los routers.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import json
import os
import re
import socket
import time
import unicodedata
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
        "dynamips_id": 1,
        "names": {"santiago"},
        "cfg": CONFIGS_DIR / "Santiago_variante1.cfg",
    },
    "valparaiso": {
        "node_id": VINA_ID,
        "dynamips_id": 2,
        "names": {"vina", "valparaiso"},
        "cfg": CONFIGS_DIR / "Vina_variante1.cfg",
    },
}

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def to_clean_ascii(text: str) -> bytes:
    """Convierte tildes/UTF-8 a ASCII puro compatible con Cisco IOS."""
    norm = unicodedata.normalize("NFKD", text)
    return norm.encode("ascii", errors="ignore")


def clean_telnet_bytes(data: bytes) -> str:
    """Elimina secuencias Telnet IAC (0xFF ...), bytes nulos (0x00) y códigos ANSI."""
    cleaned = re.sub(b"\xff[\xfb-\xfe].", b"", data)
    cleaned = re.sub(b"\xff[\xf0-\xfa]", b"", cleaned)
    cleaned = cleaned.replace(b"\x00", b"")
    text = cleaned.decode("latin-1", errors="ignore")
    return ANSI_RE.sub("", text)


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

    def _auth_header(self, req: urllib.request.Request) -> None:
        if self.cfg.user:
            token = base64.b64encode(f"{self.cfg.user}:{self.cfg.password}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")

    def request(self, method: str, endpoint: str, payload: object | None = None) -> object:
        url = f"{self.cfg.base_url}/{endpoint.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        self._auth_header(req)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    def upload_node_file(self, pid: str, nid: str, rel_path: str, raw_bytes: bytes) -> None:
        url = f"{self.cfg.base_url}/v2/projects/{pid}/nodes/{nid}/files/{rel_path.lstrip('/')}"
        req = urllib.request.Request(url, data=raw_bytes, method="POST")
        req.add_header("Content-Type", "application/octet-stream")
        self._auth_header(req)
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()

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

    def restart_node(self, pid: str, node: dict) -> dict:
        nid = node["node_id"]
        print(f"[*] Reiniciando nodo '{node['name']}' vía API GNS3...")
        self.request("POST", f"/v2/projects/{pid}/nodes/{nid}/stop", {})
        time.sleep(1.0)
        self.request("POST", f"/v2/projects/{pid}/nodes/{nid}/start", {})
        time.sleep(7.0)
        nodes: list[dict] = self.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        return next(n for n in nodes if n["node_id"] == nid)

    def ensure_topology_wiring(self, pid: str) -> None:
        """Asegura el enlace WAN principal (Fa0/0 <-> Fa0/0) y el troncal Vina Fa0/1 <-> SwitchAccesoV e0."""
        links: list[dict] = self.request("GET", f"/v2/projects/{pid}/links")  # type: ignore[assignment]
        has_main_wan = False
        has_roas_trunk = False
        for lk in links:
            eps = {(e["node_id"], e["adapter_number"], e["port_number"]) for e in lk.get("nodes", [])}
            if (SANTIAGO_ID, 0, 0) in eps and (VINA_ID, 0, 0) in eps:
                has_main_wan = True
                continue
            if (SANTIAGO_ID, 1, 0) in eps:
                print("[*] Eliminando enlace WAN secundario innecesario...")
                self.request("DELETE", f"/v2/projects/{pid}/links/{lk['link_id']}")
                continue
            if (VINA_ID, 1, 0) in eps and (SWITCH_V_ID, 0, 0) in eps:
                print("[*] Moviendo troncal de Sucursal de Vina Fa1/0 a Vina Fa0/1 (Router-on-a-Stick 802.1Q)...")
                self.request("DELETE", f"/v2/projects/{pid}/links/{lk['link_id']}")
                continue
            if (VINA_ID, 0, 1) in eps and (SWITCH_V_ID, 0, 0) in eps:
                has_roas_trunk = True

        if not has_main_wan:
            print("[*] Conectando enlace WAN principal: Santiago (Fa0/0) <-> Vina (Fa0/0)...")
            self.request(
                "POST",
                f"/v2/projects/{pid}/links",
                {
                    "nodes": [
                        {"node_id": SANTIAGO_ID, "adapter_number": 0, "port_number": 0},
                        {"node_id": VINA_ID, "adapter_number": 0, "port_number": 0},
                    ]
                },
            )

        if not has_roas_trunk:
            links = self.request("GET", f"/v2/projects/{pid}/links")  # type: ignore[assignment]
            fa01_busy = any(
                (VINA_ID, 0, 1) in {(e["node_id"], e["adapter_number"], e["port_number"]) for e in lk.get("nodes", [])}
                for lk in links
            )
            if not fa01_busy:
                print("[*] Conectando troncal 802.1Q: Vina (Fa0/1) <-> SwitchAccesoV (e0)...")
                self.request(
                    "POST",
                    f"/v2/projects/{pid}/links",
                    {
                        "nodes": [
                            {"node_id": VINA_ID, "adapter_number": 0, "port_number": 1},
                            {"node_id": SWITCH_V_ID, "adapter_number": 0, "port_number": 0},
                        ]
                    },
                )

    def ensure_lightweight_stage_ready(self) -> tuple[dict, dict[str, dict]]:
        proj = self.get_active_project()
        pid = proj["project_id"]
        self.ensure_topology_wiring(pid)

        nodes: list[dict] = self.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        started_any_router = False
        for n in nodes:
            if n.get("node_type") in ("ethernet_switch", "dynamips") and n.get("status") != "started":
                print(f"[*] Encendiendo nodo liviano '{n['name']}' ({n['node_type']})...")
                self.request("POST", f"/v2/projects/{pid}/nodes/{n['node_id']}/start", {})
                if n.get("node_type") == "dynamips":
                    started_any_router = True

        if started_any_router:
            print("[*] Esperando 7s para arranque de Cisco IOS...")
            time.sleep(7.0)

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
    """Cliente sincronizado por prompt real sobre socket Telnet/TCP para consolas Cisco IOS en Dynamips."""

    PROMPT_RE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*(?:\([A-Za-z0-9_-]+\))?[#>])\s*$")

    def __init__(self, host: str, port: int, timeout: float = 8.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.3)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def flush_input(self) -> str:
        self.sock.settimeout(0.08)
        chunks: list[bytes] = []
        try:
            while True:
                d = self.sock.recv(4096)
                if not d:
                    break
                chunks.append(d)
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(0.3)
        return clean_telnet_bytes(b"".join(chunks)) if chunks else ""

    @classmethod
    def _extract_trailing_prompt(cls, text: str) -> str:
        if not text:
            return ""
        lines = [
            re.sub(r"[\x00-\x1f\x7f]", "", ln).strip()
            for ln in text.replace("\r", "\n").split("\n")
        ]
        non_empty = [ln for ln in lines if ln]
        if not non_empty:
            return ""
        m = cls.PROMPT_RE.search(non_empty[-1])
        return m.group(1) if m else ""

    def send(self, cmd: str, timeout: float = 15.0) -> str:
        self.flush_input()
        self.sock.sendall(to_clean_ascii(cmd + "\r\n"))
        deadline = time.time() + timeout
        buf = ""
        saw_newline = cmd == ""
        idle_timeouts = 0

        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                idle_timeouts = 0
                decoded = clean_telnet_bytes(chunk)
                buf += decoded
                if "\n" in decoded or "\r" in decoded:
                    saw_newline = True
                if "--More--" in decoded:
                    self.sock.sendall(b" ")
                if saw_newline and self._extract_trailing_prompt(buf):
                    break
            except socket.timeout:
                idle_timeouts += 1
                if saw_newline and self._extract_trailing_prompt(buf):
                    break
                if cmd != "" and idle_timeouts == 4 and buf and not self._extract_trailing_prompt(buf):
                    self.sock.sendall(b"\r\n")
        return buf

    def ensure_priv_exec(self, wait_boot_seconds: float = 25.0) -> str:
        banner = self.flush_input()
        deadline = time.time() + wait_boot_seconds
        prompt = self._extract_trailing_prompt(banner)
        out = ""
        attempt = 0

        while not prompt and time.time() < deadline:
            attempt += 1
            out = self.send("", timeout=2.0)
            low = out.lower()
            if re.search(r"e{6,}", out):
                raise RuntimeError("BUSY_ERASE_FLASH")
            if "initial configuration dialog" in low:
                out = self.send("no", timeout=5.0)
            elif "confirm" in low or "--more--" in low or (attempt % 3 == 0 and not out.strip()):
                self.sock.sendall(b"\x03\r\n")
                time.sleep(0.4)
                out += self.flush_input()

            prompt = self._extract_trailing_prompt(out)
            if prompt:
                break
            time.sleep(0.6)

        if not prompt:
            sample = repr((banner + out)[-160:])
            raise RuntimeError(f"CONSOLE_TIMEOUT (¿tienes Solar-PuTTY abierto sobre este router?): {sample}")

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


def connect_healthy_console(client: GNS3Client, pid: str, node: dict) -> IOSConsole:
    host, port = client.resolve_console_target(node)
    con = IOSConsole(host, port)
    try:
        con.ensure_priv_exec(wait_boot_seconds=12.0)
        return con
    except RuntimeError as exc:
        con.close()
        print(f"  [!] Consola de {node['name']} ocupada/bloqueada ({exc}). Reiniciando router...")
        node = client.restart_node(pid, node)
        host, port = client.resolve_console_target(node)
        con = IOSConsole(host, port)
        con.ensure_priv_exec(wait_boot_seconds=35.0)
        return con


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


def push_router_config_atomic(client: GNS3Client, pid: str, router_key: str, node: dict) -> None:
    """
    Inyecta el startup-config de manera 100% atómica vía la API REST de GNS3:
    1. Detiene el router.
    2. Sube configs/i{dynamips_id}_startup-config.cfg (ASCII limpio) directo a la NVRAM de Dynamips.
    3. Enciende el router con la configuración completa ya cargada (cero errores de consola/Telnet).
    """
    info = ROUTERS[router_key]
    cfg_path: Path = info["cfg"]  # type: ignore[assignment]
    dyn_id = node.get("properties", {}).get("dynamips_id") or info["dynamips_id"]
    nid = node["node_id"]

    raw_cfg = to_clean_ascii(cfg_path.read_text(encoding="utf-8").replace("\r\n", "\n"))
    rel_file = f"configs/i{dyn_id}_startup-config.cfg"

    print(f"\n[*] Cargando atómicamente '{cfg_path.name}' en {node['name']} ({rel_file})...")
    client.request("POST", f"/v2/projects/{pid}/nodes/{nid}/stop", {})
    time.sleep(0.8)
    client.upload_node_file(pid, nid, rel_file, raw_cfg)
    client.request("POST", f"/v2/projects/{pid}/nodes/{nid}/start", {})
    print(f"[OK] '{cfg_path.name}' inyectado en NVRAM y router '{node['name']}' encendido.")


def cmd_routes(client: GNS3Client) -> None:
    proj, router_nodes = client.ensure_lightweight_stage_ready()
    for key, node in router_nodes.items():
        host, port = client.resolve_console_target(node)
        print(f"\n================ {key.upper()} ({host}:{port}) ================")
        con = connect_healthy_console(client, proj["project_id"], node)
        try:
            print(con.send("show ip interface brief | exclude unassigned", timeout=8.0))
            print(con.send("show ip route", timeout=8.0))
        finally:
            con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Control inteligente de GNS3 y routers Cisco IOS (Equipo 1)")
    parser.add_argument("--api", default=None, help="URL opcional de GNS3 Server API (autodetectada por defecto)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Consulta proyectos y nodos en GNS3 API")
    p_push = sub.add_parser("push-configs", help="Inyecta startup-config en NVRAM vía API y arranca routers/switches")
    p_push.add_argument("--router", choices=["all", "santiago", "valparaiso"], default="all")
    sub.add_parser("routes", help="Muestra interfaces activas y tablas de enrutamiento de ambos routers")

    args = parser.parse_args()
    cfg = discover_gns3_config(args.api)
    client = GNS3Client(cfg)

    if args.cmd == "status":
        cmd_status(client)
    elif args.cmd == "push-configs":
        proj = client.get_active_project()
        pid = proj["project_id"]
        client.ensure_topology_wiring(pid)

        # Asegurar switches Ethernet encendidos
        nodes: list[dict] = client.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        for n in nodes:
            if n.get("node_type") == "ethernet_switch" and n.get("status") != "started":
                client.request("POST", f"/v2/projects/{pid}/nodes/{n['node_id']}/start", {})

        router_nodes: dict[str, dict] = {}
        for key, meta in ROUTERS.items():
            for n in nodes:
                if n["node_id"] == meta["node_id"] or n["name"].lower() in meta["names"]:
                    router_nodes[key] = n
                    break

        targets = ["santiago", "valparaiso"] if args.router == "all" else [args.router]
        for t in targets:
            if t not in router_nodes:
                raise SystemExit(f"No se encontró el router '{t}' en la topología activa.")
            push_router_config_atomic(client, pid, t, router_nodes[t])

        print("\n[*] Esperando 8s a que ambos routers terminen de iniciar con su nueva NVRAM...")
        time.sleep(8.0)
        print("[LISTO] Ambos routers iniciados y configurados al 100%.")
    elif args.cmd == "routes":
        cmd_routes(client)


if __name__ == "__main__":
    main()
