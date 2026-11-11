"""Fusiones manuales (data/fusiones.csv) y su efecto en la cascada de matching.

Sin red: usa registros sintéticos con la forma que devuelven los scrapers.
Si la fusión no existe en el pipeline, el scraper semanal vuelve a dar de alta
la empresa dada de baja (ver scraper/matching.py: aplicar_fusiones).
"""
import csv
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scraper"))
matching = pytest.importorskip("matching")
from common import normalizar_nombre  # noqa: E402


def _leer(nombre):
    with open(RAIZ / "data" / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_alias_se_absorbe_en_el_canonico():
    registros = [
        {"nombre": "LOGISTICA DEL ALTO S.R.L.", "camara": "CAPEMISA", "rubro": "Logística",
         "url_ficha": "u1", "telefono": "(0387) 403 2318", "contacto_nombre": "Micaela Ohse"},
        {"nombre": "CENTRO DISTRIBUIDOR S.A.", "camara": "CAPEMISA", "rubro": "Logística",
         "url_ficha": "u2", "telefono": "(0387) 403 2318", "contacto_nombre": "Micaela Ohse"},
    ]
    fusiones = [{"alias": "CENTRO DISTRIBUIDOR S.A.", "canonico": "LOGISTICA DEL ALTO S.R.L."}]
    entidades, candidatos = matching.construir_entidades(
        matching.aplicar_fusiones(registros, fusiones))
    assert len(entidades) == 1
    assert entidades[0].campos["nombre"] == "LOGISTICA DEL ALTO S.R.L."
    assert len(entidades[0].membresias) == 1
    assert candidatos == []


def test_sin_fusiones_no_cambia_nada():
    registros = [{"nombre": "ACME S.A.", "camara": "UIS", "rubro": "Metalurgia", "url_ficha": "u"}]
    assert matching.aplicar_fusiones(registros, []) == registros


def test_alias_ya_no_existe_como_empresa_activa():
    nombres = {normalizar_nombre(e["nombre"]) for e in _leer("empresas.csv")}
    for f in _leer("fusiones.csv"):
        assert normalizar_nombre(f["alias"]) not in nombres
        assert normalizar_nombre(f["canonico"]) in nombres
