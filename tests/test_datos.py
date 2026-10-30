"""Invariantes de los datos commiteados (data/*.csv y data/empresas.json).

Corren sin red: validan el estado actual del directorio, no lo que devuelve
un scraper. Los xfail documentan decisiones pendientes (ver docs/auditoria.md),
no bugs silenciados: cuando se resuelvan, el test pasa y pytest lo avisa.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"


def leer_csv(nombre):
    with open(DATA / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def empresas():
    return leer_csv("empresas.csv")


@pytest.fixture(scope="module")
def membresias():
    return leer_csv("membresias.csv")


@pytest.fixture(scope="module")
def export_json():
    with open(DATA / "empresas.json", encoding="utf-8") as f:
        return json.load(f)["empresas"]


def test_ids_unicos(empresas):
    ids = [e["id"] for e in empresas]
    assert len(ids) == len(set(ids))


def test_nombre_norm_unico(empresas):
    norms = [e["nombre_norm"] for e in empresas]
    assert len(norms) == len(set(norms))


def test_membresias_apuntan_a_empresa_existente(empresas, membresias):
    ids = {e["id"] for e in empresas}
    huerfanas = [m for m in membresias if m["empresa_id"] not in ids]
    assert huerfanas == []


def test_toda_empresa_tiene_membresia(empresas, membresias):
    con_membresia = {m["empresa_id"] for m in membresias}
    sin = [e["nombre"] for e in empresas if e["id"] not in con_membresia]
    assert sin == []


def test_export_json_coincide_con_csv(empresas, export_json):
    assert {str(e["id"]) for e in empresas} == {str(e["id"]) for e in export_json}


def test_sitio_web_solo_http(empresas):
    malos = [e["sitio_web"] for e in empresas
             if e["sitio_web"] and not re.match(r"^https?://", e["sitio_web"], re.I)]
    assert malos == []


def test_redes_no_son_paginas_de_login_ni_share(empresas):
    patron = re.compile(r"accounts/login|/login|\?next=|sharer|originalSubdomain", re.I)
    malos = [(e["nombre"], e[red]) for e in empresas
             for red in ("instagram", "facebook", "linkedin")
             if e[red] and patron.search(e[red])]
    assert malos == []


def test_logos_son_urls_http(empresas):
    malos = [e["nombre"] for e in empresas if not re.match(r"^https?://", e["logo_url"])]
    assert malos == []


@pytest.mark.xfail(strict=False, reason="Pendiente: 26 logos en data/logos/ sin referencia (docs/auditoria.md)")
def test_no_hay_logos_huerfanos(export_json):
    usados = {Path(str(e["logo"])).name for e in export_json if e.get("logo")}
    huerfanos = sorted(p.name for p in (DATA / "logos").iterdir() if p.name not in usados)
    assert huerfanos == []


@pytest.mark.xfail(strict=False, reason="Pendiente: CENTRO DISTRIBUIDOR y LOGISTICA DEL ALTO comparten teléfono, email y representante (docs/auditoria.md)")
def test_sin_pares_con_telefono_y_email_compartidos(empresas):
    por_par = defaultdict(list)
    for e in empresas:
        if e["telefono"].strip() and e["email"].strip():
            por_par[(e["telefono"].strip(), e["email"].strip().lower())].append(e["nombre"])
    duplicados = {k: v for k, v in por_par.items() if len(v) > 1}
    assert duplicados == {}


def test_cambios_csv_tipos_validos():
    tipos = Counter(c["tipo"] for c in leer_csv("cambios.csv"))
    assert set(tipos) <= {"alta", "baja", "modificacion", "nuevo_rubro"}
