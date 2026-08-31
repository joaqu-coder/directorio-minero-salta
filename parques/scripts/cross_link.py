# -*- coding: utf-8 -*-
"""Cruce liviano por CUIT entre el sitio de cámaras (CMS/CAPEMISA/UIS) y
/parques. Solo lectura de los dos JSON — nunca escribe en ninguno de los
dos ni fusiona registros. Si el mismo CUIT existe en ambos sitios, cada
uno sigue mostrando su propia ficha; esto solo genera el dato para que
cada frontend pueda ofrecer el link "también en [otro sitio] →".

Entrada:
  ../data/empresas.csv    (sitio de cámaras, en la raíz del repo — source
                            of truth. NO se lee empresas.json: ese export
                            de scraper/build_db.py no incluye el campo
                            "cuit" — se comprobó corriendo este script.
                            Tocar build_db.py para agregarlo está fuera de
                            scope ["no tocar matching.py/build_db.py
                            actuales"], así que se lee el CSV directo —
                            sigue siendo de solo lectura, y el slug se
                            recalcula acá con la misma función y el mismo
                            orden que usa build_db.py para que salga
                            idéntico al que ya usa el frontend de cámaras)
  data/parques.json       (este sitio, generado por build_parques_db.py)

Salida: data/cruce.json, keyed por CUIT normalizado (solo dígitos). Para
cada CUIT que aparece en al menos uno de los dos sitios:
  {
    "<cuit>": {
      "en_camaras": bool, "en_parques": bool,
      "camaras": {"id", "slug", "nombre"} | null,
      "parques": [{"id", "slug", "nombre", "parque"}]  // normalmente 1 item
    }
  }
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # parques/
DATA = RAIZ / "data"
EMPRESAS_CAMARAS_CSV = RAIZ.parent / "data" / "empresas.csv"
PARQUES_JSON = DATA / "parques.json"
SALIDA = DATA / "cruce.json"


# Copia exacta de scraper/common.py::normalizar_nombre + slugificar (sin
# importar common.py: arrastra scrapling/curl_cffi solo para 2 funciones
# puras de string, igual que ya resolvió scraper/match_pig_guemes.py).
# Tiene que ser una copia BIT A BIT de la lógica real, no una
# reinterpretación: si el slug no sale idéntico al que ya usa
# index.html?empresa=slug del sitio de cámaras, el link cruzado apunta a
# una ficha que no existe.
_FORMAS_LEGALES = re.compile(
    r"\s+(s\s?a\s?p\s?e\s?m|s\s?a\s?c\s?i\s?f?\s?i?\s?a?|s\s?a\s?i\s?c\s?f?|"
    r"s\s?r\s?l|s\s?a\s?s|s\s?a\s?u|s\s?c\s?a|s\s?c\s?s|s\s?h|s\s?e|s\s?a|"
    r"ltda|srl|sas|sau|sa|inc|llc|corp|group|y\s?cia|cia|"
    r"coop(?:erativa)?(?:\s+de\s+trabajo)?(?:\s+ltda)?)\s*$"
)


def normalizar_nombre(nombre: str) -> str:
    s = nombre.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    previo = None
    while previo != s:
        previo = s
        s = _FORMAS_LEGALES.sub("", s).strip()
    return s


def slugificar_camaras(nombre: str) -> str:
    s = normalizar_nombre(nombre) or nombre.lower()
    return re.sub(r"\s+", "-", s.strip())


def normalizar_cuit(valor: str) -> str:
    """Solo dígitos. Un CUIT válido tiene 11, pero hay casos reales en las
    fuentes con un dígito de menos (ej. "3-52181759-9" en vez de
    "30-52181759-9", así cargado en cámaras Y en el Sheet de Güemes para
    la misma empresa — Cerámica Salteña). Exigir ==11 perdería ese cruce
    real. Se usa un piso de 8 dígitos solo para no matchear basura corta
    (extensión de teléfono, etc.), sin intentar "arreglar" el CUIT."""
    if not valor:
        return ""
    digitos = re.sub(r"\D", "", valor)
    return digitos if len(digitos) >= 8 else ""


def main():
    if not EMPRESAS_CAMARAS_CSV.exists():
        raise SystemExit(f"No encuentro {EMPRESAS_CAMARAS_CSV} — ¿está el repo completo?")
    if not PARQUES_JSON.exists():
        raise SystemExit(f"No encuentro {PARQUES_JSON} — correr build_parques_db.py primero.")

    with EMPRESAS_CAMARAS_CSV.open(encoding="utf-8", newline="") as f:
        empresas_camaras = list(csv.DictReader(f))
    parques = json.loads(PARQUES_JSON.read_text(encoding="utf-8"))

    por_cuit_camaras = {}
    sin_cuit_camaras = 0
    slugs_usados = set()
    for e in empresas_camaras:
        # mismo algoritmo de dedupe de slug que build_db.py, mismo orden
        # (el del CSV) — así el slug generado acá es idéntico al que ya
        # está publicado en empresas.json.
        slug = slugificar_camaras(e["nombre"])
        while slug in slugs_usados:
            slug += "-x"
        slugs_usados.add(slug)

        cuit = normalizar_cuit(e.get("cuit") or "")
        if not cuit:
            sin_cuit_camaras += 1
            continue
        # en cámaras el cuit es libre (no hay UNIQUE); si dos empresas
        # comparten cuit por error de carga, nos quedamos con la primera
        # y no rompemos el build por eso.
        por_cuit_camaras.setdefault(cuit, {"id": int(e["id"]), "slug": slug, "nombre": e["nombre"]})

    por_cuit_parques = {}
    sin_cuit_parques = 0
    for e in parques.get("empresas", []):
        cuit = normalizar_cuit(e.get("cuit") or "")
        if not cuit:
            sin_cuit_parques += 1
            continue
        por_cuit_parques.setdefault(cuit, []).append({
            "id": e["id"], "slug": e["slug"], "nombre": e["nombre"], "parque": e.get("parque"),
        })

    cuits = set(por_cuit_camaras) | set(por_cuit_parques)
    cruce = {}
    for cuit in cuits:
        en_camaras = cuit in por_cuit_camaras
        en_parques = cuit in por_cuit_parques
        cruce[cuit] = {
            "en_camaras": en_camaras,
            "en_parques": en_parques,
            "camaras": por_cuit_camaras.get(cuit),
            "parques": por_cuit_parques.get(cuit, []),
        }

    SALIDA.write_text(json.dumps(cruce, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    con_cruce = sum(1 for v in cruce.values() if v["en_camaras"] and v["en_parques"])
    print(f"OK {SALIDA.name}: {len(cruce)} CUITs, {con_cruce} con presencia en ambos sitios")
    print(f"  cámaras: {len(por_cuit_camaras)} empresas con CUIT válido, {sin_cuit_camaras} sin CUIT (no cruzables)")
    print(f"  parques: {len(por_cuit_parques)} empresas con CUIT válido, {sin_cuit_parques} sin CUIT (no cruzables)")


if __name__ == "__main__":
    main()
