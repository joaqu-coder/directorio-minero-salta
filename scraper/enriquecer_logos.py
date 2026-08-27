# -*- coding: utf-8 -*-
"""Completa logo_url (y de paso email/teléfono/redes) para empresas que ya
tienen sitio_web cargado pero ningún logo — el caso de las altas del Parque
Industrial Güemes (2026-08-27), que llegaron sin logo porque el Sheet no
traía uno.

No reinventa el fetch/extracción: reusa enriquecer_dominio() de
enriquecer.py tal cual (mismo criterio de qué es un buen logo — SVG con
"logo" en el nombre > icon SVG > raster > og:image).

Requiere red real (Scrapling) — no corre en el sandbox de desarrollo, sí en
GitHub Actions o en una máquina con salida a internet:

    python scraper/enriquecer_logos.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAIZ, normalizar_dominio  # noqa: E402
from enriquecer import enriquecer_dominio  # noqa: E402
from build_db import main as rebuild  # noqa: E402
import csv

DATA = RAIZ / "data"
CSV_EMPRESAS = DATA / "empresas.csv"

CAMPOS_COMPLEMENTARIOS = ["email", "telefono", "instagram", "facebook", "linkedin"]

# Ninguna URL, email o teléfono legítimo se acerca a esto. Un valor más largo
# es basura scrapeada (típicamente una imagen embebida en base64): guardarla
# rompe la relectura del CSV y voltea el rebuild, con lo que se pierde TODO el
# trabajo de la corrida, no solo el campo malo. Pasó el 2026-08-27: 19 logos
# scrapeados bien, descartados porque el rebuild murió después de escribirlos.
MAX_LARGO_VALOR = 2000


def valor_sano(v):
    return bool(v) and len(str(v)) <= MAX_LARGO_VALOR


def leer_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escribir_csv(path, filas):
    campos = list(filas[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def main():
    dry_run = "--dry-run" in sys.argv
    empresas = leer_csv(CSV_EMPRESAS)

    candidatas = [
        e for e in empresas
        if (e.get("sitio_web") or "").strip() and not (e.get("logo_url") or "").strip()
    ]
    print(f"{len(candidatas)} empresas con sitio_web pero sin logo_url")

    modificadas = 0
    for e in candidatas:
        dom = normalizar_dominio(e["sitio_web"])
        print(f"  {e['nombre']} ({dom})", flush=True)
        try:
            info = enriquecer_dominio(dom, e["sitio_web"])
        except Exception as exc:
            print(f"    EXCEPCION: {exc}", file=sys.stderr)
            continue
        if not info:
            print("    sin datos")
            continue

        cambios = {}
        if valor_sano(info.get("logo_url")) and not e.get("logo_url", "").strip():
            cambios["logo_url"] = info["logo_url"]
            cambios["logo_origen"] = "sitio_oficial"
        for campo in CAMPOS_COMPLEMENTARIOS:
            if valor_sano(info.get(campo)) and not e.get(campo, "").strip():
                cambios[campo] = info[campo]

        if cambios:
            e.update(cambios)
            modificadas += 1
            print(f"    + {', '.join(cambios.keys())}")

    if not modificadas:
        print("\nSin cambios.")
        return 0

    if dry_run:
        print(f"\n--dry-run: {modificadas} empresas se habrían actualizado, no se escribió nada.")
        return 0

    escribir_csv(CSV_EMPRESAS, empresas)
    print(f"\nCSV actualizado: {modificadas} empresas con logo/contacto nuevo.")

    print("Rebuilding directorio.db + empresas.json...")
    rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
