# -*- coding: utf-8 -*-
"""
enriquecer2.py — Segunda pasada de enriquecimiento directo desde empresas.csv.

Para cada empresa:
  1. Visita su sitio web (si existe) y extrae campos vacíos:
     email, teléfono, instagram, facebook, linkedin, descripción.
  2. Si aún faltan redes sociales, busca en DuckDuckGo.

Actualiza empresas.csv in-place y regenera empresas.json.
Log: data/staging/enriquecimiento2.json
"""
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, STAGING, attr, fetch, normalizar_dominio

EMPRESAS_CSV = DATA / "empresas.csv"
EMPRESAS_JSON = DATA / "empresas.json"
LOG = STAGING / "enriquecimiento2.json"

RED_PAT = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([\w.\-]{2,})/?\??"),
    "facebook":  re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|pages/category)([\w.\-]+)/?\??"),
    "linkedin":  re.compile(r"https?://(?:[\w-]+\.)?linkedin\.com/(?:company|in)/([^/?#\s]+)"),
}

ABOUT_SLUGS = ["/nosotros", "/quienes-somos", "/about", "/about-us",
               "/la-empresa", "/empresa", "/historia", "/contacto"]

RAPIDO = dict(intentos=2, delay_min=0.4, delay_max=1.0, timeout=14, verify=False)
DDG_DELAY = 3.0  # segundos entre búsquedas DuckDuckGo


def _extraer_redes(page) -> dict:
    redes = {}
    for href in page.css("a::attr(href)").getall():
        h = str(href).split("?")[0].rstrip("/")
        for red, pat in RED_PAT.items():
            if red not in redes and pat.match(h):
                redes[red] = h
    return redes


def _extraer_contacto(page) -> dict:
    info = {}
    mail = attr(page, 'a[href^="mailto:"]::attr(href)')
    if mail:
        addr = mail[7:].split("?")[0].strip()
        if "@" in addr and "example" not in addr and len(addr) < 80:
            info["email"] = addr
    tel = attr(page, 'a[href^="tel:"]::attr(href)')
    if tel:
        info["telefono"] = tel[4:].strip()
    return info


def _extraer_descripcion(page) -> str | None:
    for sel in ['meta[name="description"]::attr(content)',
                'meta[property="og:description"]::attr(content)']:
        meta = attr(page, sel)
        if meta and len(meta.strip()) > 50:
            return meta.strip()[:600]
    for p in page.css("p").getall():
        txt = re.sub(r"<[^>]+>", " ", str(p))
        txt = re.sub(r"\s+", " ", txt).strip()
        if 70 < len(txt) < 900 and not any(
            w in txt.lower() for w in ["cookie", "política de", "© ", "all rights", "powered by"]
        ):
            return txt[:600]
    return None


def enriquecer_desde_web(empresa: dict) -> dict:
    url = empresa.get("sitio_web", "").strip()
    if not url:
        return {}
    updates = {}

    page = fetch(url, **RAPIDO)
    if page is None:
        return {}

    base = str(page.url) if page.url else url

    redes = _extraer_redes(page)
    contacto = _extraer_contacto(page)

    for campo in ("instagram", "facebook", "linkedin"):
        if not empresa.get(campo) and redes.get(campo):
            updates[campo] = redes[campo]
    for campo in ("email", "telefono"):
        if not empresa.get(campo) and contacto.get(campo):
            updates[campo] = contacto[campo]
    if not empresa.get("descripcion"):
        d = _extraer_descripcion(page)
        if d:
            updates["descripcion"] = d

    # Subpáginas si aún falta descripción o alguna red social
    faltan_redes = any(
        not empresa.get(r) and not updates.get(r)
        for r in ("instagram", "facebook", "linkedin")
    )
    falta_desc = not empresa.get("descripcion") and not updates.get("descripcion")
    if faltan_redes or falta_desc:
        for slug in ABOUT_SLUGS:
            aurl = urljoin(base, slug)
            if aurl == base:
                continue
            apage = fetch(aurl, **RAPIDO)
            if apage and apage.status == 200:
                redes2 = _extraer_redes(apage)
                for campo in ("instagram", "facebook", "linkedin"):
                    if not empresa.get(campo) and not updates.get(campo) and redes2.get(campo):
                        updates[campo] = redes2[campo]
                if falta_desc and not updates.get("descripcion"):
                    d = _extraer_descripcion(apage)
                    if d:
                        updates["descripcion"] = d
            if not faltan_redes and not falta_desc:
                break

    return updates


def buscar_en_ddg(nombre: str, red: str) -> str | None:
    """Busca perfil de red social en DuckDuckGo HTML (sin API)."""
    query = f'"{nombre}" site:{red}.com'
    url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    time.sleep(DDG_DELAY)
    page = fetch(url, intentos=1, delay_min=0, delay_max=0.1, timeout=15, verify=False)
    if page is None:
        return None
    pat = RED_PAT[red]
    for href in page.css("a::attr(href)").getall():
        h = str(href).split("?")[0].rstrip("/")
        m = pat.match(h)
        if m:
            user = m.group(1)
            if user.lower() not in ("p", "reel", "explore", "stories", "sharer",
                                    "plugins", "home", "login", "company", "in"):
                return h
    # DuckDuckGo a veces wrappea en /l/?uddg=... — busca en el texto de los links
    for a_text in page.css("a.result__url").getall():
        raw = re.sub(r"<[^>]+>", "", str(a_text)).strip()
        m = pat.match("https://" + raw.lstrip("/"))
        if m:
            user = m.group(1)
            if user.lower() not in ("p", "reel", "explore", "stories", "login"):
                return "https://" + raw.lstrip("/")
    return None


def regenerar_json(rows: list, fieldnames: list):
    """Regenera empresas.json desde las filas actualizadas."""
    data = []
    for r in rows:
        obj = {k: v for k, v in r.items() if v}
        data.append(obj)
    EMPRESAS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"  empresas.json regenerado: {len(data)} registros")


def main():
    if not EMPRESAS_CSV.exists():
        sys.exit(f"No existe {EMPRESAS_CSV}")
    STAGING.mkdir(parents=True, exist_ok=True)

    with open(EMPRESAS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    total = len(rows)
    print(f"Cargadas {total} empresas.")

    log_cambios = {}
    actualizadas = 0

    # ── Pasada 1: enriquecimiento desde sitio web ───────────────────────────
    print("\n── Pasada 1: sitios web ──────────────────────────────────────────")
    for i, empresa in enumerate(rows, 1):
        falta = [c for c in ("email", "telefono", "instagram", "facebook",
                              "linkedin", "descripcion")
                 if not empresa.get(c, "").strip()]
        if not empresa.get("sitio_web", "").strip() or not falta:
            continue
        tag = f"[{i}/{total}] {empresa['nombre'][:38]}"
        print(f"  {tag}...", end=" ", flush=True)
        try:
            ups = enriquecer_desde_web(empresa)
        except Exception as e:
            print(f"ERROR {e}")
            continue
        if ups:
            print(f"+{', '.join(ups)}")
            empresa.update(ups)
            log_cambios.setdefault(empresa["id"], {}).update(ups)
            actualizadas += 1
        else:
            print("—")

    # ── Pasada 2: búsqueda DuckDuckGo para redes faltantes ─────────────────
    print("\n── Pasada 2: búsqueda DDG para redes sociales faltantes ──────────")
    busquedas = 0
    for i, empresa in enumerate(rows, 1):
        nombre = empresa.get("nombre", "").strip()
        if not nombre:
            continue
        for red in ("instagram", "linkedin", "facebook"):
            if empresa.get(red, "").strip():
                continue
            tag = f"[{i}/{total}] {nombre[:35]} → {red}"
            print(f"  {tag}...", end=" ", flush=True)
            try:
                url = buscar_en_ddg(nombre, red)
            except Exception as e:
                print(f"ERROR {e}")
                continue
            busquedas += 1
            if url:
                print(f"✓ {url}")
                empresa[red] = url
                log_cambios.setdefault(empresa["id"], {})[red] = url
                actualizadas += 1
            else:
                print("—")

    # ── Guardar resultados ──────────────────────────────────────────────────
    with open(EMPRESAS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  empresas.csv actualizado")

    LOG.write_text(
        json.dumps(log_cambios, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  log: {LOG} ({len(log_cambios)} empresas con cambios)")

    regenerar_json(rows, fieldnames)

    print(f"\nFIN: {actualizadas} actualizaciones en {len(log_cambios)} empresas.")
    print(f"  búsquedas DDG realizadas: {busquedas}")


if __name__ == "__main__":
    main()
