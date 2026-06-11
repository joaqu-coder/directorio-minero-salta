# -*- coding: utf-8 -*-
"""Scraper de cmsalta.com.ar (Cámara de la Minería de Salta) -> staging/cms.json"""
import re
import sys

from common import attr, fetch, guardar_staging, registro, texto

BASE = "https://cmsalta.com.ar"


def logo_tamano_completo(src: str) -> str:
    """WordPress sirve thumbnails -150x150; el original está sin sufijo."""
    return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", src) if src else src


def scrape_lista():
    page = fetch(f"{BASE}/socios/")
    if page is None:
        sys.exit("No se pudo descargar la lista de socios de CMS")
    socios = []
    for li in page.css("ul.sucursales-list li"):
        nombre = texto(li, "span.info h5::text")
        link = attr(li, f'a[href*="{BASE}/asociados/"]::attr(href)')
        if not nombre or not link:
            continue
        logo = attr(li, "span.logo img::attr(src)")
        socios.append({
            "nombre": nombre,
            "url_ficha": link,
            "logo_url": logo_tamano_completo(logo),
            "ubicacion": texto(li, "span.info p::text"),
        })
    return socios


def scrape_detalle(url: str) -> dict:
    page = fetch(url)
    if page is None:
        return {}
    datos = {}
    contenedor = page.css("div.datos").first
    if contenedor:
        etiquetas = [str(h).rstrip(": ").strip() for h in contenedor.css("h6::text").getall()]
        valores = [str(p).strip() for p in contenedor.css("p::text").getall()]
        datos = dict(zip(etiquetas, valores))
    web = None
    for href in page.css('div.datos-container a[href^="http"]::attr(href)'):
        if "cmsalta.com.ar" not in str(href):
            web = str(href)
            break
    return {
        "actividad": datos.get("Actividades"),
        "mineral": datos.get("Mineral"),
        "fase": datos.get("Fase del Proyecto"),
        "producto": datos.get("Producto final"),
        "direccion": datos.get("Dirección") or datos.get("Direccion"),
        "sitio_web": web,
    }


def main():
    socios = scrape_lista()
    print(f"CMS lista: {len(socios)} socios")
    registros = []
    for s in socios:
        det = scrape_detalle(s["url_ficha"])
        partes = []
        descripcion = None
        if det.get("actividad"):
            # algunas fichas traen una descripción narrativa larga en vez
            # de una actividad corta: va a descripcion, no a actividad
            if len(det["actividad"]) > 160:
                descripcion = det["actividad"]
            else:
                partes.append(det["actividad"])
        if det.get("mineral"):
            partes.append(f"Mineral: {det['mineral']}")
        if det.get("fase"):
            partes.append(f"Fase: {det['fase']}")
        if det.get("producto") and det.get("producto") != det.get("mineral"):
            partes.append(f"Producto: {det['producto']}")
        registros.append(registro(
            camara="CMS",
            rubro="Minería",
            nombre=s["nombre"],
            actividad=" — ".join(partes) or None,
            direccion=det.get("direccion"),
            sitio_web=det.get("sitio_web"),
            logo_url=s["logo_url"],
            url_ficha=s["url_ficha"],
            ubicacion=s["ubicacion"],
            descripcion=descripcion,
        ))
        print(f"  {s['nombre']}")
    if len(registros) < 25:
        sys.exit(f"FALLO validación: CMS devolvió {len(registros)} (< 25). Revisar selectores.")
    guardar_staging("cms.json", registros)


if __name__ == "__main__":
    main()
