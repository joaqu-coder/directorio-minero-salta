# -*- coding: utf-8 -*-
"""Reduce los logos de data/logos/ a un máximo de 320 px por lado.

Los logos se muestran a 96-200 px (CSS), pero había archivos de hasta 988 KB.
Mantiene nombre y formato (el ajuste de tonos de ajustar_logos.py referencia
los archivos por nombre). SVG y placeholders de la cámara no se tocan.

Uso: python scraper/reducir_logos.py [--max 320] [--dry-run]
"""
import argparse
import hashlib
import io
from pathlib import Path

from PIL import Image

from build_db import PLACEHOLDER_MD5  # noqa: E402  (mismo conjunto que la exportación)
from common import RAIZ

LOGOS = RAIZ / "data" / "logos"


def reducir(ruta: Path, maximo: int, dry_run: bool):
    original = ruta.read_bytes()
    if hashlib.md5(original).hexdigest() in PLACEHOLDER_MD5:
        return None
    img = Image.open(io.BytesIO(original))
    if max(img.size) <= maximo:
        return None
    formato = img.format
    img.thumbnail((maximo, maximo), Image.LANCZOS)
    buf = io.BytesIO()
    if formato == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
    else:
        img.save(buf, "PNG", optimize=True)
    nuevo = buf.getvalue()
    if len(nuevo) >= len(original):
        return None
    if not dry_run:
        ruta.write_bytes(nuevo)
    return len(original), len(nuevo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=320)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    antes = despues = n = 0
    for ruta in sorted(LOGOS.iterdir()):
        if ruta.suffix.lower() not in (".png", ".jpg", ".jpeg", ".jfif"):
            continue
        r = reducir(ruta, args.max, args.dry_run)
        if r:
            n += 1
            antes += r[0]
            despues += r[1]
    print(f"{n} logos reducidos: {antes/1e6:.1f} MB -> {despues/1e6:.1f} MB"
          + (" (dry-run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
