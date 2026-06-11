# -*- coding: utf-8 -*-
"""Utilidades compartidas por los scrapers del Directorio Minero Salta."""
import json
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

from scrapling.fetchers import Fetcher

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
STAGING = DATA / "staging"

# Delay entre requests al MISMO dominio (cámaras). Para enriquecimiento
# (dominios distintos) se usa un delay menor.
DELAY_MIN, DELAY_MAX = 2.0, 3.0

_ultimo_request = 0.0

# Formas legales al final del nombre, ya sin puntuación y en minúsculas.
_FORMAS_LEGALES = re.compile(
    r"\s+(s\s?a\s?p\s?e\s?m|s\s?a\s?c\s?i\s?f?\s?i?\s?a?|s\s?a\s?i\s?c\s?f?|"
    r"s\s?r\s?l|s\s?a\s?s|s\s?a\s?u|s\s?c\s?a|s\s?c\s?s|s\s?h|s\s?e|s\s?a|"
    r"ltda|srl|sas|sau|sa|inc|llc|corp|group|y\s?cia|cia|"
    r"coop(?:erativa)?(?:\s+de\s+trabajo)?(?:\s+ltda)?)\s*$"
)


def normalizar_nombre(nombre: str) -> str:
    """lowercase, sin tildes, sin formas legales, sin puntuación."""
    s = nombre.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    previo = None
    while previo != s:  # puede haber más de una forma legal encadenada
        previo = s
        s = _FORMAS_LEGALES.sub("", s).strip()
    return s


def normalizar_dominio(url: str) -> str:
    """Dominio sin esquema, sin www, sin path. '' si no hay URL usable."""
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("/")[0].split("?")[0].strip()
    return u if "." in u else ""


def slugificar(nombre: str) -> str:
    s = normalizar_nombre(nombre) or nombre.lower()
    return re.sub(r"\s+", "-", s.strip())


def fetch(url: str, intentos: int = 3, delay_min: float = None, delay_max: float = None,
          timeout: int = 30, verify: bool = True):
    """GET con rate-limit y reintentos. Devuelve la Response de Scrapling o None."""
    global _ultimo_request
    lo = DELAY_MIN if delay_min is None else delay_min
    hi = DELAY_MAX if delay_max is None else delay_max
    for intento in range(1, intentos + 1):
        espera = random.uniform(lo, hi) - (time.time() - _ultimo_request)
        if espera > 0:
            time.sleep(espera)
        _ultimo_request = time.time()
        try:
            page = Fetcher.get(
                url, stealthy_headers=True, follow_redirects=True,
                timeout=timeout, retries=1, verify=verify,  # retries=0 rompe la sesión de Scrapling
            )
            if page.status == 200:
                return page
            print(f"  [{page.status}] {url} (intento {intento})", file=sys.stderr)
        except Exception as e:
            print(f"  [ERROR] {url}: {e} (intento {intento})", file=sys.stderr)
        time.sleep(2 * intento)
    return None


def guardar_staging(nombre_archivo: str, registros: list):
    STAGING.mkdir(parents=True, exist_ok=True)
    destino = STAGING / nombre_archivo
    destino.write_text(
        json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"OK {destino.name}: {len(registros)} registros")


def cargar_staging(nombre_archivo: str) -> list:
    destino = STAGING / nombre_archivo
    if not destino.exists():
        return []
    return json.loads(destino.read_text(encoding="utf-8"))


def texto(nodo, selector: str):
    """Primer resultado de texto del selector, limpio, o None."""
    t = nodo.css(selector).get()
    if t is None:
        return None
    limpio = t.clean() if hasattr(t, "clean") else str(t).strip()
    return str(limpio) if limpio else None


def attr(nodo, selector: str):
    """Primer atributo que matchee el selector (::attr(...)), o None."""
    a = nodo.css(selector).get()
    return str(a) if a else None


def registro(**kw) -> dict:
    """Registro staging con todos los campos presentes."""
    base = {
        "camara": None, "rubro": None, "nombre": None, "actividad": None,
        "direccion": None, "telefono": None, "email": None, "sitio_web": None,
        "contacto_nombre": None, "logo_url": None, "logo_placeholder": False,
        "url_ficha": None, "ubicacion": None, "descripcion": None,
    }
    base.update(kw)
    return base
