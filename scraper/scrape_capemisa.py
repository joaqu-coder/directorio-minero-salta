# -*- coding: utf-8 -*-
"""Scraper de capemisa.com.ar -> staging/capemisa.json

Las cards de cada página de categoría traen todos los campos, así que no
hace falta visitar las fichas individuales. La paginación es server-side
(/categoria/page/N/) con 20 cards por página.
"""
import sys

from common import attr, fetch, guardar_staging, registro, texto

BASE = "https://capemisa.com.ar"

# slug de URL -> nombre de rubro (16 categorías verificadas junio 2026)
CATEGORIAS = {
    "alquiler-de-vehiculos": "Alquiler de vehículos",
    "catering": "Catering",
    "comunicaciones": "Comunicaciones",
    "consultoria": "Consultoría",
    "construccion": "Construcción",
    "energia": "Energía",
    "equipamiento": "Equipamiento",
    "5316-2": "Geomembrana",
    "ingenieria": "Ingeniería",
    "insumos": "Insumos",
    "logistica": "Logística",
    "medicina": "Medicina",
    "perforaciones": "Perforaciones",
    "seguridad": "Seguridad",
    "servicios": "Servicios",
    "topografia": "Topografía",
}

CAMPOS = {
    "actividad": "actividad",
    "dirección": "direccion",
    "direccion": "direccion",
    "teléfono": "telefono",
    "telefono": "telefono",
    "email": "email",
    "contacto": "contacto_nombre",
}


def parsear_card(card, rubro):
    nombre = texto(card, "h3.elementor-heading-title::text")
    if not nombre:
        return None
    datos = {}
    sitio_web = None
    for item in card.css("li.elementor-icon-list-item"):
        link = attr(item, 'a[href^="http"]::attr(href)')
        cuerpo = texto(item, "span.elementor-icon-list-text::text") or ""
        if link and "capemisa.com.ar" not in link:
            sitio_web = link
            continue
        if ":" in cuerpo:
            clave, _, valor = cuerpo.partition(":")
            clave = clave.strip().lower()
            if clave in CAMPOS and valor.strip():
                datos[CAMPOS[clave]] = valor.strip()
    logo = attr(card, "img::attr(src)")
    placeholder = bool(logo and "logocapemisa" in logo.lower())
    return registro(
        camara="CAPEMISA",
        rubro=rubro,
        nombre=nombre,
        actividad=datos.get("actividad"),
        direccion=datos.get("direccion"),
        telefono=datos.get("telefono"),
        email=datos.get("email"),
        sitio_web=sitio_web,
        contacto_nombre=datos.get("contacto_nombre"),
        logo_url=logo,
        logo_placeholder=placeholder,
        url_ficha=attr(card, f'a[href*="{BASE}/socio/"]::attr(href)'),
    )


def scrape_categoria(slug, rubro):
    regs = []
    pagina = 1
    while True:
        url = f"{BASE}/{slug}/" if pagina == 1 else f"{BASE}/{slug}/page/{pagina}/"
        page = fetch(url)
        if page is None:
            break
        cards = page.css("article.elementor-post.type-socio")
        nuevos = [r for r in (parsear_card(c, rubro) for c in cards) if r]
        # /page/N/ fuera de rango repite contenido en algunos WordPress:
        # cortar si no aparecen nombres nuevos.
        conocidos = {r["nombre"] for r in regs}
        nuevos = [r for r in nuevos if r["nombre"] not in conocidos]
        if not nuevos:
            break
        regs.extend(nuevos)
        if len(cards) < 20:
            break
        pagina += 1
    print(f"  {rubro}: {len(regs)}")
    return regs


def main():
    registros = []
    for slug, rubro in CATEGORIAS.items():
        registros.extend(scrape_categoria(slug, rubro))
    nombres_unicos = {r["nombre"] for r in registros}
    print(f"CAPEMISA: {len(registros)} membresías, {len(nombres_unicos)} empresas únicas")
    if len(nombres_unicos) < 100:
        sys.exit(f"FALLO validación: CAPEMISA devolvió {len(nombres_unicos)} empresas (< 100).")
    guardar_staging("capemisa.json", registros)


if __name__ == "__main__":
    main()
