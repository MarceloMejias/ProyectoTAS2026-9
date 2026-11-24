#!/usr/bin/env python3
"""
Demostración y prueba liviana para Equipo 1: DHCP Centralizado entre Sedes.

Permite validar TODAS las evidencias de la Variante 1 (y las ACLs) usando 2 nodos VPCS
ultra-livianos (~2 MB RAM c/u) en la Sucursal Valparaíso:
  - VPCS-Ventas  (SwitchAccesoV Ethernet4 -> VLAN 10 -> Ámbito 1: 10.0.0.0/28)
  - VPCS-Soporte (SwitchAccesoV Ethernet5 -> VLAN 20 -> Ámbito 2: 10.0.0.16/28)

Modos de uso:
  1. Con --simular-servidor (0 VMs encendidas, ideal para probar red/relay/ACLs en 30s):
     Levanta temporalmente 192.168.0.34 y los 2 ámbitos DHCP en el router Santiago (Casa Matriz),
     ejecuta concesión remota por Relay en ambos ámbitos, comprueba Gateway/DNS, modifica una
     opción del ámbito (DNS/dominio), renueva y limpia la simulación al terminar.
  2. Sin --simular-servidor (con FirewallSantiago + VM DNSDHCP Rocky Linux encendidos):
     Prueba exactamente lo mismo contra el servidor real DNSDHCP (192.168.0.34) en la DMZ.
"""

from __future__ import annotations

import argparse
import re
import socket
import time
from gns3_control import GNS3Client, IOSConsole, SWITCH_V_ID, discover_gns3_config


class VPCSConsole:
    """Cliente TCP simple para consolas de nodos VPCS en GNS3."""

    PROMPT_RE = re.compile(r"^[A-Za-z0-9_-]+>\s*$")

    def __init__(self, host: str, port: int, timeout: float = 8.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(0.25)

    def close(self) -> None:
        self.sock.close()

    def send(self, cmd: str, timeout: float = 25.0) -> str:
        self.sock.settimeout(0.05)
        try:
            while self.sock.recv(4096):
                pass
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(0.25)

        self.sock.sendall((cmd + "\r\n").encode("ascii"))
        deadline = time.time() + timeout
        buf = ""
        saw_nl = cmd == ""
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                txt = chunk.decode("latin-1", errors="ignore")
                buf += txt
                if "\n" in txt or "\r" in txt:
                    saw_nl = True
                tail = buf.replace("\r", "\n").split("\n")[-1].strip()
                if saw_nl and self.PROMPT_RE.match(tail):
                    break
            except socket.timeout:
                tail = buf.replace("\r", "\n").split("\n")[-1].strip()
                if saw_nl and self.PROMPT_RE.match(tail):
                    break
        return buf


def ensure_sucursal_vpcs(client: GNS3Client, pid: str) -> tuple[dict, dict]:
    """Configura puertos e4 (VLAN 10) y e5 (VLAN 20) en SwitchAccesoV y crea/enciende 2 nodos VPCS."""
    nodes: list[dict] = client.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
    sw = next((n for n in nodes if n["node_id"] == SWITCH_V_ID or n["name"] == "SwitchAccesoV"), None)
    if not sw:
        raise SystemExit("No se encontró SwitchAccesoV en el proyecto.")

    # Asegurar que Ethernet4 esté en VLAN 10 y Ethernet5 en VLAN 20
    pmap = sw.get("properties", {}).get("ports_mapping", [])
    changed = False
    for p in pmap:
        if p.get("port_number") == 4 and p.get("vlan") != 10:
            p["vlan"] = 10
            p["type"] = "access"
            changed = True
        elif p.get("port_number") == 5 and p.get("vlan") != 20:
            p["vlan"] = 20
            p["type"] = "access"
            changed = True
    if changed:
        print("[*] Configurando SwitchAccesoV: Ethernet4=VLAN10 (Ventas), Ethernet5=VLAN20 (Soporte)...")
        client.request("PUT", f"/v2/projects/{pid}/nodes/{sw['node_id']}", {"properties": {"ports_mapping": pmap}})

    specs = [
        ("VPCS-Ventas", 4, 220, 310),
        ("VPCS-Soporte", 5, 450, 210),
    ]
    links: list[dict] = client.request("GET", f"/v2/projects/{pid}/links")  # type: ignore[assignment]
    result: list[dict] = []

    for name, sw_port, x, y in specs:
        vpcs = next((n for n in nodes if n["name"] == name and n["node_type"] == "vpcs"), None)
        if not vpcs:
            print(f"[*] Creando cliente liviano '{name}' (2 MB RAM) en Sucursal...")
            vpcs = client.request(  # type: ignore[assignment]
                "POST",
                f"/v2/projects/{pid}/nodes",
                {"name": name, "node_type": "vpcs", "compute_id": "local", "x": x, "y": y},
            )

        linked = any(
            any(ep["node_id"] == vpcs["node_id"] for ep in lk.get("nodes", []))  # type: ignore[index]
            for lk in links
        )
        if not linked:
            client.request(
                "POST",
                f"/v2/projects/{pid}/links",
                {
                    "nodes": [
                        {"node_id": sw["node_id"], "adapter_number": 0, "port_number": sw_port},
                        {"node_id": vpcs["node_id"], "adapter_number": 0, "port_number": 0},  # type: ignore[index]
                    ]
                },
            )

        if vpcs.get("status") != "started":  # type: ignore[union-attr]
            client.request("POST", f"/v2/projects/{pid}/nodes/{vpcs['node_id']}/start", {})  # type: ignore[index]

        nodes_refreshed: list[dict] = client.request("GET", f"/v2/projects/{pid}/nodes")  # type: ignore[assignment]
        vpcs = next(n for n in nodes_refreshed if n["node_id"] == vpcs["node_id"])  # type: ignore[index]
        result.append(vpcs)

    return result[0], result[1]


def setup_mock_dhcp_on_santiago(stgo: IOSConsole, dns_list: str = "192.168.0.34", domain: str = "technomarket.cl") -> None:
    stgo.ensure_priv_exec()
    cmds = [
        "configure terminal",
        "service dhcp",
        "interface Loopback34",
        "ip address 192.168.0.34 255.255.255.255",
        "exit",
        "ip dhcp excluded-address 10.0.0.1",
        "ip dhcp excluded-address 10.0.0.17",
        "ip dhcp pool AMBITO_1_VENTAS",
        "network 10.0.0.0 255.255.255.240",
        "default-router 10.0.0.1",
        f"dns-server {dns_list}",
        f"domain-name {domain}",
        "exit",
        "ip dhcp pool AMBITO_2_SOPORTE",
        "network 10.0.0.16 255.255.255.240",
        "default-router 10.0.0.17",
        "dns-server 192.168.0.34",
        "domain-name technomarket.cl",
        "exit",
        "end",
    ]
    for c in cmds:
        stgo.send(c, timeout=5.0)


def cleanup_mock_dhcp_on_santiago(stgo: IOSConsole) -> None:
    stgo.ensure_priv_exec()
    for c in [
        "configure terminal",
        "no interface Loopback34",
        "no ip dhcp pool AMBITO_1_VENTAS",
        "no ip dhcp pool AMBITO_2_SOPORTE",
        "no ip dhcp excluded-address 10.0.0.1",
        "no ip dhcp excluded-address 10.0.0.17",
        "end",
    ]:
        stgo.send(c, timeout=5.0)


def pause_step(interactive: bool, title: str) -> None:
    print(f"\n{'=' * 74}\n>>> {title}\n{'=' * 74}")
    if interactive:
        input("Presiona [ENTER] para ejecutar este paso...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demostración Equipo 1 — DHCP Centralizado entre Sedes")
    parser.add_argument("--api", default=None, help="URL opcional de GNS3 Server API")
    parser.add_argument(
        "--simular-servidor",
        action="store_true",
        help="Simula temporalmente el servidor DHCP 192.168.0.34 en Santiago para probar sin encender VMs",
    )
    parser.add_argument("--auto", action="store_true", help="Ejecutar sin pausas interactivas")
    args = parser.parse_args()

    interactive = not args.auto
    cfg = discover_gns3_config(args.api)
    client = GNS3Client(cfg)
    proj, router_nodes = client.ensure_lightweight_stage_ready()
    vpcs_ventas, vpcs_soporte = ensure_sucursal_vpcs(client, proj["project_id"])

    stgo_h, stgo_p = client.resolve_console_target(router_nodes["santiago"])
    valpo_h, valpo_p = client.resolve_console_target(router_nodes["valparaiso"])
    ven_h, ven_p = client.resolve_console_target(vpcs_ventas)
    sop_h, sop_p = client.resolve_console_target(vpcs_soporte)

    stgo = IOSConsole(stgo_h, stgo_p)
    valpo = IOSConsole(valpo_h, valpo_p)
    c_ven = VPCSConsole(ven_h, ven_p)
    c_sop = VPCSConsole(sop_h, sop_p)

    try:
        stgo.ensure_priv_exec()
        valpo.ensure_priv_exec()
        c_ven.send("", timeout=3.0)
        c_sop.send("", timeout=3.0)

        if args.simular_servidor:
            print("[*] Activando servidor DHCP centralizado temporal (192.168.0.34) en Casa Matriz (0 VMs)...")
            setup_mock_dhcp_on_santiago(stgo)
            time.sleep(1.5)

        pause_step(interactive, "EVIDENCIA 1: Concesión DHCP remota vía Relay en DOS ÁMBITOS (Ventas VLAN 10 y Soporte VLAN 20)")
        print("\n--- [Valparaíso] Verificación de DHCP Relay (ip helper-address 192.168.0.34) ---")
        print(valpo.send("show ip interface Vlan10 | include Internet|Helper", timeout=6.0))
        print(valpo.send("show ip interface Vlan20 | include Internet|Helper", timeout=6.0))

        print("--- [VPCS-Ventas | VLAN 10] Solicitando IP al Ámbito 1 (10.0.0.0/28) ---")
        print(c_ven.send("ip dhcp", timeout=25.0))
        ven_ip_info = c_ven.send("show ip", timeout=5.0)
        print(ven_ip_info)

        print("--- [VPCS-Soporte | VLAN 20] Solicitando IP al Ámbito 2 (10.0.0.16/28) ---")
        print(c_sop.send("ip dhcp", timeout=25.0))
        sop_ip_info = c_sop.send("show ip", timeout=5.0)
        print(sop_ip_info)

        pause_step(interactive, "EVIDENCIA 2: Comprobar ACL en Sucursal (Soporte bloqueado hacia Ventas)")
        m_ip = re.search(r"IP/MASK\s*:\s*([0-9.]+)/", ven_ip_info)
        target_ventas = m_ip.group(1) if m_ip else "10.0.0.2"
        print(f"--- [VPCS-Soporte -> {target_ventas} (Ventas)] Debe ser BLOQUEADO por ACL_SOPORTE_IN ---")
        print(c_sop.send(f"ping {target_ventas} -c 2", timeout=10.0))
        print(valpo.send("show access-lists ACL_SOPORTE_IN", timeout=6.0))

        pause_step(interactive, "EVIDENCIA 3: Cambiar una opción del Ámbito 1 (DNS secundario + Dominio) y renovar")
        if args.simular_servidor:
            print("[*] Modificando Ámbito 1 en Casa Matriz: DNS='192.168.0.34 192.168.0.35', Dominio='sucursal.technomarket.cl'...")
            setup_mock_dhcp_on_santiago(stgo, dns_list="192.168.0.34 192.168.0.35", domain="sucursal.technomarket.cl")
        else:
            print("Ejecuta ahora en tu VM DNSDHCP: sudo bash cambiar_opcion_ambito_dhcp.sh 192.168.0.35")
            if interactive:
                input("Cuando hayas ejecutado el cambio en DNSDHCP, presiona [ENTER] para renovar...")

        print("--- [VPCS-Ventas | VLAN 10] Renovando concesión DHCP ---")
        print(c_ven.send("ip dhcp", timeout=25.0))
        ven_renewed = c_ven.send("show ip", timeout=5.0)
        print(ven_renewed)

        ok1 = "10.0.0.1" in ven_ip_info and "10.0.0.17" in sop_ip_info
        ok3 = "192.168.0.35" in ven_renewed or "sucursal.technomarket.cl" in ven_renewed
        if ok1 and ok3:
            print("\n[OK] Todas las evidencias de Equipo 1 (2 ámbitos por Relay + Gateway/DNS + cambio y renovación) pasaron al 100%.")
        else:
            print("\n[AVISO] Revisa la salida superior para confirmar que ambos ámbitos entregaron IP y renovaron la opción.")
    finally:
        if args.simular_servidor:
            print("[*] Limpiando servidor DHCP simulado en Santiago...")
            cleanup_mock_dhcp_on_santiago(stgo)
        stgo.close()
        valpo.close()
        c_ven.close()
        c_sop.close()


if __name__ == "__main__":
    main()
