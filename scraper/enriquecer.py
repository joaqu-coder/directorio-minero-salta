# -*- coding: utf-8 -*-
"""Segunda pasada: visita el sitio oficial de cada empresa y extrae
logo de calidad, email, teléfono y redes sociales.

Salida: data/staging/enriquecimiento.json  { dominio: {campos...} }

Cada request va a un dominio distinto, así que el delay entre requests
es mínimo (no hay rate-limit que respetar por host).
"""
import json
import re
import sys
from urllib.parse import urljoin

from common import STAGING, attr, cargar_staging, fetch, normalizar_dominio

# dominios que no son sitios corporativos
NO_SITIOS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "wa.me", "api.whatsapp.com", "goo.gl", "maps.app.goo.gl",
}

RED_SOCIAL = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.\-]+/?$"),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share)[\w.\-]+/?$"),
    "linkedin": re.compile(r"https?://(?:[\w]+\.)?linkedin\.com/(?:company|in)/[^/?#]+/?$"),
}


def extraer_logo(page, base_url):
    """Mejor logo disponible. Preferencia: <img> con 'logo' en SVG >
    icon SVG > <img> logo raster > og:image > icon raster."""
    candidatos = []  # (prioridad, url)
    for src in page.css("img::attr(src)").getall():
        s = str(src)
        if "logo" in s.lower():
            prio = 0 if s.lower().split("?")[0].endswith(".svg") else 2
            candidatos.append((prio, s))
    for link in page.css('link[rel*="icon"]::attr(href)').getall():
        s = str(link)
        prio = 1 if s.lower().split("?")[0].endswith(".svg") else 4
        candidatos.append((prio, s))
    og = attr(page, 'meta[property="og:image"]::attr(content)')
    if og:
        candidatos.append((3, og))
    if not candidatos:
        return None, False
    candidatos.sort(key=lambda c: c[0])
    url = urljoin(base_url, candidatos[0][1])
    return url, url.lower().split("?")[0].endswith(".svg")


RAPIDO = dict(intentos=1, delay_min=0.2, delay_max=0.5, timeout=10, verify=False)


def enriquecer_dominio(dominio, url_original):
    url = url_original if url_original.startswith("http") else f"https://{dominio}/"
    page = fetch(url, **RAPIDO)
    if page is None and normalizar_dominio(url) != dominio:
        page = fetch(f"https://{dominio}/", **RAPIDO)
    if page is None:
        return None

    info = {}
    logo, es_svg = extraer_logo(page, str(page.url) if page.url else url)
    if logo:
        info["logo_url"] = logo
        info["logo_es_svg"] = es_svg

    mail = attr(page, 'a[href^="mailto:"]::attr(href)')
    if mail:
        direccion = mail[7:].split("?")[0].strip()
        if "@" in direccion:
            info["email"] = direccion
    tel = attr(page, 'a[href^="tel:"]::attr(href)')
    if tel:
        info["telefono"] = tel[4:].strip()

    for a in page.css("a::attr(href)").getall():
        h = str(a)
        for red, patron in RED_SOCIAL.items():
            if red not in info and patron.match(h.split("?")[0]):
                info[red] = h.split("?")[0]

    tw = attr(page, 'meta[name="twitter:site"]::attr(content)') or attr(
        page, 'meta[name="twitter:creator"]::attr(content)')
    if tw:
        info["twitter"] = tw
    return info or None


def main():
    registros = (
        cargar_staging("cms.json")
        + cargar_staging("capemisa.json")
        + cargar_staging("uis.json")
    )
    if not registros:
        sys.exit("Sin staging: correr los scrapers primero.")

    dominios = {}
    for r in registros:
        dom = normalizar_dominio(r.get("sitio_web") or "")
        if dom and dom not in NO_SITIOS and dom not in dominios:
            dominios[dom] = r["sitio_web"]

    print(f"Enriqueciendo {len(dominios)} dominios...")
    resultado = {}
    fallidos = 0
    for i, (dom, url) in enumerate(sorted(dominios.items()), 1):
        try:
            info = enriquecer_dominio(dom, url)
        except Exception as e:
            print(f"  [{i}/{len(dominios)}] {dom}: EXCEPCION {e}", file=sys.stderr)
            info = None
        if info:
            resultado[dom] = info
            print(f"  [{i}/{len(dominios)}] {dom}: {', '.join(info.keys())}", flush=True)
        else:
            fallidos += 1
            print(f"  [{i}/{len(dominios)}] {dom}: sin datos", flush=True)

    STAGING.mkdir(parents=True, exist_ok=True)
    (STAGING / "enriquecimiento.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"OK enriquecimiento.json: {len(resultado)} dominios con datos, {fallidos} sin datos")


if __name__ == "__main__":
    main()
