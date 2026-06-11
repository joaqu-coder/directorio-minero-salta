# -*- coding: utf-8 -*-
"""Scraper de uis.com.ar (Unión Industrial de Salta) -> staging/uis.json

Listado paginado server-side: /asociados/?sf_paged=N (24 por página).
Cada ficha /socios/{slug}/ tiene logo, nombre, rubro, ubicación, descripción
y bloque .datos-asociado con dirección, teléfono, email y sitio web.
"""
import sys

from common import attr, fetch, guardar_staging, registro, texto

BASE = "https://uis.com.ar"

ICONOS = {
    "fa-location-dot": "direccion",
    "fa-phone": "telefono",
    "fa-envelope": "email",
}


def scrape_lista():
    """Devuelve {url_ficha: logo_url} de todas las páginas del listado."""
    socios = {}
    pagina = 1
    while True:
        page = fetch(f"{BASE}/asociados/?sf_paged={pagina}")
        if page is None:
            break
        nuevos = 0
        for card in page.css("li.card_item"):
            link = attr(card, f'a[href*="{BASE}/socios/"]::attr(href)')
            if not link or link in socios:
                continue
            socios[link] = attr(card, "img::attr(src)")
            nuevos += 1
        if nuevos == 0:
            break
        pagina += 1
    return socios


def scrape_detalle(url, logo_listado):
    page = fetch(url)
    if page is None:
        return None
    nombre = texto(page, "section#page-header .content h2::text")
    if not nombre:
        return None
    datos_spans = [str(s).strip() for s in page.css("section#page-header .datos span.empresa::text").getall()]
    rubro = datos_spans[0] if datos_spans else None
    ubicacion = datos_spans[1] if len(datos_spans) > 1 else None
    descripcion = " ".join(
        str(p).strip() for p in page.css("#entry-content .hentry p::text").getall()
    ).strip() or None

    campos = {}
    for div in page.css("div.datos-asociado > div"):
        icono = attr(div, "i::attr(class)") or ""
        valor = texto(div, "h6::text")
        for clase, campo in ICONOS.items():
            if clase in icono and valor:
                campos[campo] = valor
        if "fa-globe" in icono:
            web = attr(div, "a::attr(href)")
            if web:
                campos["sitio_web"] = web

    logo = attr(page, "section#page-header .logo img::attr(src)")
    return registro(
        camara="UIS",
        rubro=rubro,
        nombre=nombre,
        actividad=rubro,
        direccion=campos.get("direccion"),
        telefono=campos.get("telefono"),
        email=campos.get("email"),
        sitio_web=campos.get("sitio_web"),
        logo_url=logo or logo_listado,
        url_ficha=url,
        ubicacion=ubicacion,
        descripcion=descripcion,
    )


def main():
    socios = scrape_lista()
    print(f"UIS lista: {len(socios)} socios")
    registros = []
    for url, logo in socios.items():
        reg = scrape_detalle(url, logo)
        if reg:
            registros.append(reg)
            print(f"  {reg['nombre']}")
    if len(registros) < 50:
        sys.exit(f"FALLO validación: UIS devolvió {len(registros)} (< 50). Revisar selectores.")
    guardar_staging("uis.json", registros)


if __name__ == "__main__":
    main()
