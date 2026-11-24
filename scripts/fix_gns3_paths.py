#!/usr/bin/env python3
"""
Utilidad offline para adaptar ProyectoTAS.gns3 de Linux (/home/victor/...) a Windows:
1. inspect:          Muestra nodos, imágenes, rutas VMX y enlaces actuales.
2. fix-vmware-paths: Corrige las rutas Linux (/home/victor/...) en ProyectoTAS.gns3 y limpia
                     ISOs/pipes de Linux dentro de los archivos .vmx del proyecto.
3. set-ios:          Actualiza el nombre/MD5 de la imagen IOS c2691 si usas otra versión.

Importante: Cierra GNS3 antes de ejecutar comandos que modifiquen ProyectoTAS.gns3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GNS3 = ROOT / "gns3" / "ProyectoTAS" / "ProyectoTAS" / "ProyectoTAS.gns3"


def backup_file(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak_script")
    shutil.copy2(path, bak)
    return bak


def clean_linux_vmx(vmx_file: Path) -> None:
    """Elimina referencias a /home/victor/*.iso y pipes /tmp/... en archivos .vmx exportados desde Linux."""
    lines = vmx_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#!/usr/bin/vmware"):
            continue
        if re.match(r'^(ide\d+:\d+|sata\d+:\d+)\.filename\s*=\s*"/home/.*"', stripped):
            prefix = stripped.split(".")[0]
            out.append(f'{prefix}.filename = ""')
            out.append(f'{prefix}.present = "FALSE"')
            continue
        if re.match(r'^(ide\d+:\d+|sata\d+:\d+)\.present\s*=\s*"TRUE"', stripped):
            continue
        if stripped.startswith("filesearchpath") and "/home/" in stripped:
            out.append('filesearchpath = "."')
            continue
        if stripped.startswith("serial0.") and ("/tmp/" in stripped or "present" in stripped):
            if "present" in stripped:
                out.append('serial0.present = "FALSE"')
            continue
        out.append(line)
    vmx_file.write_text("\n".join(out) + "\n", encoding="utf-8")


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


def cmd_fix_vmware_paths(gns3_path: Path) -> None:
    data = json.loads(gns3_path.read_text(encoding="utf-8"))
    vmware_dir = gns3_path.parent / "project-files" / "vmware"
    pfsense_standalone = (ROOT / "vmware" / "pfSense" / "FirewallSantiago.vmx").resolve()
    bak = backup_file(gns3_path)

    fixed_nodes = 0
    for node in data["topology"]["nodes"]:
        if node.get("node_type") != "vmware":
            continue
        if node.get("name") == "FirewallSantiago" and pfsense_standalone.exists():
            node["properties"]["vmx_path"] = str(pfsense_standalone)
            node["properties"]["linked_clone"] = False
            fixed_nodes += 1
            print(f"[OK] {node['name']:24s} -> {pfsense_standalone}")
            continue

        node_id = node["node_id"]
        old_vmx = node.get("properties", {}).get("vmx_path", "")
        vmx_name = Path(old_vmx).name
        local_vmx = (vmware_dir / node_id / vmx_name).resolve()
        if local_vmx.exists():
            clean_linux_vmx(local_vmx)
            node["properties"]["vmx_path"] = str(local_vmx)
            fixed_nodes += 1
            print(f"[OK] {node['name']:24s} -> {local_vmx}")
        else:
            print(f"[WARN] No se encontró archivo VMX local para {node['name']}: {local_vmx}")

    gns3_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"\nRespaldo guardado en: {bak}")
    print(f"Rutas VMX corregidas en {fixed_nodes} nodos.")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Utilidad para inspeccionar y ajustar ProyectoTAS.gns3")
    parser.add_argument("--gns3", type=Path, default=DEFAULT_GNS3, help="Ruta a ProyectoTAS.gns3")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("inspect", help="Muestra nodos, imágenes, rutas VMX y enlaces actuales")
    sub.add_parser("fix-vmware-paths", help="Convierte rutas VMX de /home/victor/... a rutas locales de Windows")

    p_ios = sub.add_parser("set-ios", help="Cambia la imagen IOS de los routers c2691")
    p_ios.add_argument("image_path", type=Path, help="Ruta al archivo .image/.bin que tienes en GNS3\\images\\IOS")

    args = parser.parse_args()
    if not args.gns3.exists():
        raise SystemExit(f"No se encontró el archivo GNS3 en: {args.gns3}")

    if args.action == "inspect":
        cmd_inspect(args.gns3)
    elif args.action == "fix-vmware-paths":
        cmd_fix_vmware_paths(args.gns3)
    elif args.action == "set-ios":
        cmd_set_ios(args.gns3, args.image_path)


if __name__ == "__main__":
    main()
