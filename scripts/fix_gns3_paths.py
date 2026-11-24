#!/usr/bin/env python3
"""
Utilidad offline para adaptar ProyectoTAS.gns3 en Windows:
1. Permite actualizar el nombre/MD5 de la imagen IOS c2691 si usas otra versión.
2. Permite inyectar el segundo enlace WAN de Capa 3 (Variante 9):
   Santiago (Fa1/0) <-> Vina (Fa0/1) si aún no existe en la topología.

Importante: Cierra el proyecto en GNS3 antes de ejecutar modificaciones.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GNS3 = ROOT / "gns3" / "ProyectoTAS" / "ProyectoTAS" / "ProyectoTAS.gns3"

SANTIAGO_ID = "19d852b9-922e-4eec-ab39-248aa419245b"
VINA_ID = "4f30d82d-9494-4bb1-8abd-e751783ac5a3"


def backup_file(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak_script")
    shutil.copy2(path, bak)
    return bak


def cmd_inspect(gns3_path: Path) -> None:
    data = json.loads(gns3_path.read_text(encoding="utf-8"))
    nodes = {n["node_id"]: n for n in data["topology"]["nodes"]}
    print(f"Proyecto: {data.get('name')} (GNS3 v{data.get('version')})")
    print("\n--- Nodos ---")
    for n in nodes.values():
        props = n.get("properties", {})
        extra = ""
        if n["node_type"] == "dynamips":
            extra = f" | IOS={props.get('image')} | Telnet={n.get('console')}"
        elif n["node_type"] == "vmware":
            extra = f" | VMX={props.get('vmx_path')}"
        print(f"- {n['name']:24s} ({n['node_type']}){extra}")

    print("\n--- Enlaces ---")
    for link in data["topology"]["links"]:
        a, b = link["nodes"]
        na = nodes[a["node_id"]]["name"]
        nb = nodes[b["node_id"]]["name"]
        print(
            f"- {na} ({a['adapter_number']}/{a['port_number']}) <-> "
            f"{nb} ({b['adapter_number']}/{b['port_number']})"
        )


def cmd_set_ios(gns3_path: Path, image_file: Path) -> None:
    if not image_file.exists():
        raise SystemExit(f"No existe el archivo de imagen: {image_file}")

    md5 = hashlib.md5(image_file.read_bytes()).hexdigest()
    data = json.loads(gns3_path.read_text(encoding="utf-8"))
    bak = backup_file(gns3_path)

    updated = 0
    for node in data["topology"]["nodes"]:
        if node.get("node_type") == "dynamips":
            node["properties"]["image"] = image_file.name
            node["properties"]["image_md5sum"] = md5
            updated += 1

    gns3_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"Respaldo creado en: {bak}")
    print(f"Actualizados {updated} routers a imagen '{image_file.name}' (md5={md5}).")


def cmd_add_backup_link(gns3_path: Path) -> None:
    data = json.loads(gns3_path.read_text(encoding="utf-8"))
    links = data["topology"]["links"]

    for link in links:
        endpoints = {
            (ep["node_id"], ep["adapter_number"], ep["port_number"])
            for ep in link["nodes"]
        }
        if (SANTIAGO_ID, 1, 0) in endpoints or (VINA_ID, 0, 1) in endpoints:
            print("Ya existe un enlace usando Santiago Fa1/0 o Vina Fa0/1. No se realizaron cambios.")
            return

    bak = backup_file(gns3_path)
    new_link = {
        "filters": {},
        "link_id": str(uuid.uuid4()),
        "link_style": {"color": "#0084ff", "type": 1, "width": 2},
        "nodes": [
            {
                "adapter_number": 1,
                "label": {
                    "rotation": 0,
                    "style": "font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #0084ff;fill-opacity: 1.0;",
                    "text": "f1/0 (Backup)",
                    "x": 68,
                    "y": 42,
                },
                "node_id": SANTIAGO_ID,
                "port_number": 0,
            },
            {
                "adapter_number": 0,
                "label": {
                    "rotation": 0,
                    "style": "font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #0084ff;fill-opacity: 1.0;",
                    "text": "f0/1 (Backup)",
                    "x": -35,
                    "y": 42,
                },
                "node_id": VINA_ID,
                "port_number": 1,
            },
        ],
        "suspend": False,
    }
    links.append(new_link)
    gns3_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"Respaldo creado en: {bak}")
    print("Enlace de respaldo agregado: Santiago Fa1/0 <-> Vina Fa0/1 (10.10.10.4/30).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Utilidad para inspeccionar y ajustar ProyectoTAS.gns3")
    parser.add_argument("--gns3", type=Path, default=DEFAULT_GNS3, help="Ruta a ProyectoTAS.gns3")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("inspect", help="Muestra nodos, imágenes, rutas VMX y enlaces actuales")

    p_ios = sub.add_parser("set-ios", help="Cambia la imagen IOS de los routers c2691")
    p_ios.add_argument("image_path", type=Path, help="Ruta al archivo .image/.bin que tienes en GNS3\\images\\IOS")

    sub.add_parser("add-backup-link", help="Agrega el 2do enlace WAN (Santiago Fa1/0 <-> Vina Fa0/1) para Variante 9")

    args = parser.parse_args()
    if not args.gns3.exists():
        raise SystemExit(f"No se encontró el archivo GNS3 en: {args.gns3}")

    if args.action == "inspect":
        cmd_inspect(args.gns3)
    elif args.action == "set-ios":
        cmd_set_ios(args.gns3, args.image_path)
    elif args.action == "add-backup-link":
        cmd_add_backup_link(args.gns3)


if __name__ == "__main__":
    main()
