"""Guarda contra scrapes incompletos (scraper/matching.py: verificar_caida).

Sin red: usa datos sintéticos con la forma de empresas.csv / membresias.csv.
El caso de 2026-08-31 (-41 bajas) debe abortar; una semana normal debe pasar.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))
matching = pytest.importorskip("matching")


def _mundo(n_capemisa=100, n_uis=50):
    """Estado previo: n_capemisa empresas en CAPEMISA y n_uis en UIS, todas activas."""
    previas, memb = {}, []
    eid = 0
    for cam, n in (("CAPEMISA", n_capemisa), ("UIS", n_uis)):
        for i in range(n):
            eid += 1
            previas[f"{cam}-{i}"] = {"id": str(eid), "nombre_norm": f"{cam}-{i}", "estado": "activa"}
            memb.append({"empresa_id": str(eid), "camara": cam, "rubro": "", "url_ficha": ""})
    return previas, memb


def _entidades(mapa):
    """mapa: {nombre_norm: camara} -> entidades con sus membresías."""
    return [SimpleNamespace(membresias=[(cam, "", None)]) for cam in mapa.values()]


def test_semana_normal_pasa():
    previas, memb = _mundo()
    vistas = {n for n in previas if not n.endswith("-0")}  # 1 baja real
    ent = _entidades({n: n.split("-")[0] for n in vistas})
    matching.verificar_caida(previas, memb, ent, vistas)  # no debe lanzar


def test_caida_de_agosto_aborta():
    # 41 empresas de UIS desaparecen de golpe (como la corrida del 2026-08-31)
    previas, memb = _mundo(n_capemisa=100, n_uis=50)
    vistas = {n for n in previas if not n.startswith("UIS") or int(n.split("-")[1]) >= 41}
    ent = _entidades({n: n.split("-")[0] for n in vistas})
    with pytest.raises(SystemExit, match="ABORTADO"):
        matching.verificar_caida(previas, memb, ent, vistas)


def test_perdida_de_membresias_aborta_por_camara():
    # Las 100 empresas siguen activas (0 bajas), pero 40 dejan de figurar en CAPEMISA:
    # la regla por cámara debe frenar lo que la regla de bajas no ve.
    previas, memb = _mundo(n_capemisa=100, n_uis=0)
    vistas = set(previas)
    ent = [SimpleNamespace(membresias=[("CAPEMISA" if i < 60 else "UIS", "", None)])
           for i in range(100)]
    with pytest.raises(SystemExit, match="CAPEMISA pasó de 100 a 60"):
        matching.verificar_caida(previas, memb, ent, vistas)


def test_permitir_caida_saltea_la_guarda(monkeypatch):
    previas, memb = _mundo(n_capemisa=100, n_uis=50)
    vistas = set()
    monkeypatch.setenv("PERMITIR_CAIDA", "1")
    matching.verificar_caida(previas, memb, [], vistas)  # no debe lanzar


def test_primera_corrida_no_aplica():
    matching.verificar_caida({}, [], [], set())  # no debe lanzar
