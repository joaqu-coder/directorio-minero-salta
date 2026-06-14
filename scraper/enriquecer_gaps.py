# -*- coding: utf-8 -*-
"""
Enriquecimiento de gaps en empresas.csv:

  1. sitio_web vacío → revisita fichas CAPEMISA individuales (cards pueden
     omitir el link si el layout Elementor lo trunca)
  2. contacto_nombre vacío (CAPEMISA) → misma ficha individual
  3. Por cada nuevo dominio encontrado → extrae email, tel, redes sociales
  4. Actualiza empresas.csv (solo llena campos vacíos, nunca sobreescribe)
  5. Rebuild directorio.db + empresas.json

Requiere acceso a capemisa.com.ar. Corre bien desde GitHub Actions
y desde máquinas con IP residencial; puede fallar desde entornos cloud
corporativos bloqueados por Cloudflare.
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent))
from common import RAIZ, attr, fetch, normalizar_dominio

DATA = RAIZ / "data"
CSV_EMPRESAS = DATA / "empresas.csv"
CSV_MEMS     = DATA / "membresias.csv"

# Sitios que no son el sitio oficial de la empresa
EXCLUIR_DOMINIOS = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "wa.me", "whatsapp.com", "capemisa.com.ar",
    "cmsalta.com.ar", "uis.com.ar",
}

RED_SOCIAL = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.\-]+/?$"),
    "facebook":  re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share)[\w.\-]+/?$"),
    "linkedin":  re.compile(r"https?://(?:[\w]+\.)?linkedin\.com/(?:company|in)/[^/?#]+/?$"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def leer_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escribir_csv(path, rows):
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def extraer_desde_ficha_capemisa(url: str) -> dict:
    """Visita /socio/{slug}/ y devuelve campos que puedan faltar."""
    page = fetch(url, intentos=2)
    if page is None:
        return {}

    datos = {}

    # Web: primer link externo que no sea de capemisa/redes
    for a in page.css('a[href^="http"]::attr(href)').getall():
        href = str(a)
        dom = normalizar_dominio(href)
        if dom and dom not in EXCLUIR_DOMINIOS:
            datos["sitio_web"] = href
            break

    # Contacto: li items con prefijo "Contacto:"
    for item in page.css("li.elementor-icon-list-item"):
        cuerpo = ""
        t = item.css("span.elementor-icon-list-text::text").get()
        if t:
            cuerpo = str(t).strip() if not hasattr(t, "clean") else str(t.clean()).strip()
        if cuerpo.lower().startswith("contacto:"):
            val = cuerpo.partition(":")[2].strip()
            if val:
                datos["contacto_nombre"] = val
                break

    return datos


def extraer_desde_sitio(url: str) -> dict:
    """Visita el home de un sitio y extrae email, tel, redes."""
    page = fetch(url, intentos=1, delay_min=0.3, delay_max=0.8,
                 timeout=10, verify=False)
    if page is None:
        return {}

    datos = {}
    mail = attr(page, 'a[href^="mailto:"]::attr(href)')
    if mail:
        addr = mail[7:].split("?")[0].strip()
        if "@" in addr:
            datos["email"] = addr

    tel = attr(page, 'a[href^="tel:"]::attr(href)')
    if tel:
        datos["telefono"] = tel[4:].strip()

    for a in page.css("a::attr(href)").getall():
        h = str(a)
        for red, patron in RED_SOCIAL.items():
            if red not in datos and patron.match(h.split("?")[0]):
                datos[red] = h.split("?")[0]

    return datos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    empresas = leer_csv(CSV_EMPRESAS)
    mems     = leer_csv(CSV_MEMS)

    # índice empresa_id → empresa
    por_id = {e["id"]: e for e in empresas}

    # fichas CAPEMISA por empresa_id (puede haber varias si tiene múltiples rubros)
    fichas_capemisa = {}
    for m in mems:
        if m["camara"] == "CAPEMISA" and m.get("url_ficha"):
            fichas_capemisa.setdefault(m["empresa_id"], m["url_ficha"])

    sin_web      = [e for e in empresas if not e.get("sitio_web", "").strip()]
    sin_contacto = [e for e in empresas if not e.get("contacto_nombre", "").strip()]

    print(f"Gap inicial  → sin web: {len(sin_web)} | sin contacto: {len(sin_contacto)}")

    actualizaciones = {}  # empresa_id → {campo: valor}

    # ------------------------------------------------------------------
    # Fase 1: CAPEMISA fichas individuales
    # ------------------------------------------------------------------
    candidatos_capemisa = set()
    for e in sin_web:
        if e["id"] in fichas_capemisa:
            candidatos_capemisa.add(e["id"])
    for e in sin_contacto:
        if e["id"] in fichas_capemisa:
            candidatos_capemisa.add(e["id"])

    print(f"\nFase 1 — CAPEMISA fichas individuales: {len(candidatos_capemisa)} empresas")
    nuevos_web = 0
    nuevos_contacto = 0

    for eid in sorted(candidatos_capemisa):
        empresa = por_id[eid]
        url = fichas_capemisa[eid]
        print(f"  {empresa['nombre']}", flush=True)
        extra = extraer_desde_ficha_capemisa(url)
        upd = {}

        if not empresa.get("sitio_web", "").strip() and extra.get("sitio_web"):
            upd["sitio_web"] = extra["sitio_web"]
            nuevos_web += 1

        if not empresa.get("contacto_nombre", "").strip() and extra.get("contacto_nombre"):
            upd["contacto_nombre"] = extra["contacto_nombre"]
            nuevos_contacto += 1

        if upd:
            actualizaciones.setdefault(eid, {}).update(upd)
            print(f"    + {', '.join(upd.keys())}: {list(upd.values())}")

    print(f"  → Nuevos: web={nuevos_web}, contacto={nuevos_contacto}")

    # ------------------------------------------------------------------
    # Fase 2: enriquecer nuevos dominios encontrados
    # ------------------------------------------------------------------
    nuevos_dominios = {
        eid: upd["sitio_web"]
        for eid, upd in actualizaciones.items()
        if "sitio_web" in upd
    }

    if nuevos_dominios:
        print(f"\nFase 2 — Enriqueciendo {len(nuevos_dominios)} nuevos dominios")
        for eid, url in nuevos_dominios.items():
            empresa = por_id[eid]
            dom = normalizar_dominio(url)
            print(f"  {empresa['nombre']} ({dom})", flush=True)
            extra = extraer_desde_sitio(url)
            upd = {}
            for campo in ("email", "telefono", "instagram", "facebook", "linkedin"):
                if not empresa.get(campo, "").strip() and extra.get(campo):
                    upd[campo] = extra[campo]
            if upd:
                actualizaciones.setdefault(eid, {}).update(upd)
                print(f"    + {', '.join(upd.keys())}")
    else:
        print("\nFase 2 — Sin nuevos dominios que enriquecer.")

    # ------------------------------------------------------------------
    # Fase 3: aplicar cambios y rebuild
    # ------------------------------------------------------------------
    if not actualizaciones:
        print("\nSin cambios — CSV no modificado.")
        return 0

    modificadas = 0
    for e in empresas:
        upd = actualizaciones.get(e["id"])
        if not upd:
            continue
        for campo, val in upd.items():
            if campo in e and not e[campo].strip() and val:
                e[campo] = val
        modificadas += 1

    escribir_csv(CSV_EMPRESAS, empresas)
    print(f"\nCSV actualizado: {modificadas} empresas modificadas.")

    # Rebuild DB + JSON
    print("Rebuilding directorio.db + empresas.json...")
    build_script = Path(__file__).parent / "build_db.py"
    result = subprocess.run(
        [sys.executable, str(build_script)],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    # Resumen final
    empresas_actualizadas = leer_csv(CSV_EMPRESAS)
    sin_web_final = sum(1 for e in empresas_actualizadas if not e.get("sitio_web", "").strip())
    sin_contacto_final = sum(1 for e in empresas_actualizadas if not e.get("contacto_nombre", "").strip())
    print(f"\nResumen final → sin web: {sin_web_final} | sin contacto: {sin_contacto_final}")
    print(f"Mejorado      → web +{len(sin_web) - sin_web_final} | contacto +{len(sin_contacto) - sin_contacto_final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
