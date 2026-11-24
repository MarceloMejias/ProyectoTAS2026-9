#!/usr/bin/env python3
"""
Demostración automatizada / interactiva para Equipo 9: Redundancia de Enrutamiento.
Ejecuta las 3 evidencias exigidas en el PDF conectándose por consola a Santiago y Valparaíso:
  1. Comprobar ruta principal activa (via 10.10.10.2 / 10.10.10.1, AD=1) y ping entre sedes.
  2. Deshabilitar enlace principal (Fa0/0 shutdown) y comprobar conmutación al respaldo (10.10.10.6 / 10.10.10.5, AD=10).
  3. Restaurar enlace principal (Fa0/0 no shutdown) y comprobar retorno automático.
"""

from __future__ import annotations

import argparse
import time
from gns3_control import IOSConsole


def pause_step(interactive: bool, title: str) -> None:
    print(f"\n{'=' * 72}\n>>> {title}\n{'=' * 72}")
    if interactive:
        input("Presiona [ENTER] para ejecutar este paso...")


def show_wan_state(stgo: IOSConsole, valpo: IOSConsole) -> None:
    print("\n--- [Santiago] Rutas estáticas hacia Sucursal (10.0.0.x) ---")
    print(stgo.send("show ip route static", pause=0.5))
    print("--- [Valparaíso] Ruta por defecto hacia Casa Matriz ---")
    print(valpo.send("show ip route static", pause=0.5))
    print("--- [Santiago -> VLAN Ventas 10.0.0.1] Prueba de conectividad ---")
    print(stgo.send("ping 10.0.0.1 repeat 4", pause=1.5))


def main() -> None:
    parser = argparse.ArgumentParser(description="Script de demostración en vivo - Variante 9")
    parser.add_argument("--host", default="127.0.0.1", help="Host de GNS3")
    parser.add_argument("--stgo-port", type=int, default=5000, help="Puerto consola de Santiago")
    parser.add_argument("--valpo-port", type=int, default=5001, help="Puerto consola de Valparaíso/Vina")
    parser.add_argument("--auto", action="store_true", help="Ejecutar sin pausas de teclado")
    args = parser.parse_args()

    interactive = not args.auto
    stgo = IOSConsole(args.host, args.stgo_port)
    valpo = IOSConsole(args.host, args.valpo_port)

    try:
        stgo.ensure_priv_exec()
        valpo.ensure_priv_exec()

        pause_step(interactive, "EVIDENCIA 1: Verificar camino principal activo (Fa0/0 - 10.10.10.0/30, AD=1)")
        show_wan_state(stgo, valpo)

        pause_step(interactive, "EVIDENCIA 2: Simular caída de enlace principal (shutdown en Fa0/0) y probar conmutación")
        stgo.send("configure terminal", pause=0.3)
        stgo.send("interface FastEthernet0/0", pause=0.3)
        stgo.send("shutdown", pause=0.5)
        stgo.send("end", pause=0.3)
        # También bajamos extremo remoto por si Dynamips no propaga link-state de inmediato
        valpo.send("configure terminal", pause=0.3)
        valpo.send("interface FastEthernet0/0", pause=0.3)
        valpo.send("shutdown", pause=0.5)
        valpo.send("end", pause=0.3)
        time.sleep(1.5)
        show_wan_state(stgo, valpo)

        pause_step(interactive, "EVIDENCIA 3: Restaurar enlace principal (no shutdown en Fa0/0) y verificar retorno")
        stgo.send("configure terminal", pause=0.3)
        stgo.send("interface FastEthernet0/0", pause=0.3)
        stgo.send("no shutdown", pause=0.5)
        stgo.send("end", pause=0.3)
        valpo.send("configure terminal", pause=0.3)
        valpo.send("interface FastEthernet0/0", pause=0.3)
        valpo.send("no shutdown", pause=0.5)
        valpo.send("end", pause=0.3)
        time.sleep(2.0)
        show_wan_state(stgo, valpo)

        print("\n[OK] Demostración de Variante 9 completada exitosamente.")
    finally:
        stgo.close()
        valpo.close()


if __name__ == "__main__":
    main()
