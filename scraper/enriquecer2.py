# -*- coding: utf-8 -*-
"""
enriquecer2.py — Enriquecimiento incremental (solo empresas nuevas).

Lee data/cambios.csv para identificar altas del último run y enriquece
ÚNICAMENTE esas empresas — no re-procesa todo el CSV.

Sin pasada DuckDuckGo: costosa y bloqueada. Solo visita el sitio web
de cada empresa nueva para extraer campos faltantes.

Uso:
    python enriquecer2.py            # procesa altas desde cambios.csv
    python enriquecer2.py --id 42    # fuerza enriquecimiento de una empresa
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, STAGING, normalizar_dominio

EMPRESAS_CSV = DATA / "empresas.csv"
CAMBIOS_CSV = DATA / "cambios.csv"
EMPRESAS_JSON = DATA / "empresas.json"
LOG = STAGING / "enriquecimiento2.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}

RED_PAT = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([\w.\-]{2,})/?"),
    "facebook":  re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|pages/category)([\w.\-]+)/?"),
    "linkedin":  re.compile(r"https?://(?:[\w-]+\.)?linkedin\.com/(?:company|in)/([^/?#\s]+)"),
}

ABOUT_SLUGS = ["/nosotros", "/about", "/quienes-somos", "/la-empresa", "/contacto"]


def get(url: str, timeout: int = 10) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout,
                         allow_redirects=True, verify=False)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def extraer(html: str, base: str) -> dict:
    info = {}
    # Redes sociales
    for href in re.findall(r'href=["\']([^"\']+)["\']', html):
        h = href.split("?")[0].rstrip("/")
        for red, pat in RED_PAT.items():
            if red not in info and pat.match(h):
                user = pat.match(h).group(1)
                if user.lower() not in ("p", "reel", "explore", "stories", "login",
                                        "sharer", "company", "in", "home"):
                    info[red] = h
    # Email
    m = re.search(r'mailto:([^\s"\'<>?]+)', html)
    if m:
        addr = m.group(1).split("?")[0].strip()
        if "@" in addr and "example" not in addr:
            info["email"] = addr
    # Teléfono
    m = re.search(r'tel:([+\d\s\-().]+)', html)
    if m:
        info["telefono"] = m.group(1).strip()
    # Descripción (meta primero)
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I)
    if not m:
        m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', html, re.I)
    if m and len(m.group(1).strip()) > 50:
        info["descripcion"] = m.group(1).strip()[:500]
    return info


def enriquecer_empresa(empresa: dict) -> dict:
    url = empresa.get("sitio_web", "").strip()
    if not url or not normalizar_dominio(url):
        return {}

    resp = get(url)
    if resp is None:
        return {}

    updates = {}
    base = resp.url

    datos = extraer(resp.text, base)
    for campo in ("instagram", "facebook", "linkedin", "email", "telefono", "descripcion"):
        if not empresa.get(campo) and datos.get(campo):
            updates[campo] = datos[campo]

    # Subpágina About solo si falta descripción
    if not empresa.get("descripcion") and not updates.get("descripcion"):
        for slug in ABOUT_SLUGS:
            r2 = get(urljoin(base, slug))
            if r2:
                d2 = extraer(r2.text, base)
                if d2.get("descripcion"):
                    updates["descripcion"] = d2["descripcion"]
                # Redes también
                for campo in ("instagram", "facebook", "linkedin"):
                    if not empresa.get(campo) and not updates.get(campo) and d2.get(campo):
                        updates[campo] = d2[campo]
                break

    return updates


def ids_altas_recientes() -> set[str]:
    """Lee cambios.csv y devuelve IDs de empresas con tipo='alta'."""
    if not CAMBIOS_CSV.exists():
        return set()
    with open(CAMBIOS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {r["empresa_id"] for r in reader if r.get("tipo") == "alta"}


def regenerar_json(rows: list):
    data = [{k: v for k, v in r.items() if v} for r in rows]
    EMPRESAS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"  empresas.json regenerado ({len(data)} registros)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, help="Forzar enriquecimiento de empresa por ID")
    parser.add_argument("--all", action="store_true", help="Procesar todas (solo para primera corrida)")
    args = parser.parse_args()

    if not EMPRESAS_CSV.exists():
        sys.exit(f"No existe {EMPRESAS_CSV}")
    STAGING.mkdir(parents=True, exist_ok=True)

    with open(EMPRESAS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    indice = {r["id"]: i for i, r in enumerate(rows)}

    # Determinar qué IDs procesar
    if args.id:
        ids = {args.id}
    elif args.all:
        ids = set(indice.keys())
    else:
        ids = ids_altas_recientes()

    if not ids:
        print("Sin altas nuevas en cambios.csv — nada que enriquecer.")
        return

    candidatas = [rows[indice[i]] for i in ids if i in indice]
    print(f"Enriqueciendo {len(candidatas)} empresa(s) nuevas...")

    log = {}
    actualizadas = 0

    for empresa in candidatas:
        nombre = empresa.get("nombre", "")[:40]
        falta = [c for c in ("instagram", "facebook", "linkedin", "email", "descripcion")
                 if not empresa.get(c, "").strip()]
        if not falta:
            print(f"  {nombre}: completa, skip")
            continue
        print(f"  {nombre} (faltan: {', '.join(falta)})...", end=" ", flush=True)
        ups = enriquecer_empresa(empresa)
        if ups:
            print(f"+{', '.join(ups)}")
            rows[indice[empresa['id']]].update(ups)
            log[empresa["id"]] = ups
            actualizadas += 1
        else:
            print("sin nuevos datos")

    # Guardar
    with open(EMPRESAS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    regenerar_json(rows)

    print(f"\nFin: {actualizadas}/{len(candidatas)} empresas actualizadas.")


if __name__ == "__main__":
    main()
