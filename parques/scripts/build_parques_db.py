# -*- coding: utf-8 -*-
"""CSV normalizados (source of truth) -> SQLite (parques.db) + JSON
estático (parques.json) para el frontend de /parques.

Mismo patrón que scraper/build_db.py del sitio de cámaras, adaptado al
esquema catastral (parques / lotes / matrículas / empresas_parque) en vez
del esquema de membresías por rubro.
"""
import csv
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # parques/
DATA = RAIZ / "data"
DB = RAIZ / "parques.db"

ESQUEMA = """
CREATE TABLE parques (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
);

CREATE TABLE empresas_parque (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    cuit TEXT,
    rubro TEXT,
    situacion TEXT,
    contacto_nombre TEXT,
    telefono_1 TEXT,
    telefono_2 TEXT,
    email_1 TEXT,
    email_2 TEXT,
    direccion TEXT,
    pagina_web TEXT,
    instagram TEXT,
    facebook TEXT
);

CREATE TABLE lotes (
    id INTEGER PRIMARY KEY,
    parque_id INTEGER REFERENCES parques(id),
    numero TEXT,
    superficie_m2 TEXT
);

CREATE TABLE matriculas (
    id INTEGER PRIMARY KEY,
    lote_id INTEGER REFERENCES lotes(id),
    numero_matricula TEXT,
    empresa_id INTEGER REFERENCES empresas_parque(id),
    titularidad TEXT,
    estado TEXT,
    observacion TEXT
);
"""


def leer_csv(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# Copia exacta de scraper/common.py::normalizar_nombre (incluye el
# stripping de formas legales — sin esto los slugs de acá quedaban más
# largos y con un criterio distinto al resto del repo, ej.
# "zozzoli-colchones-s-a" en vez de "zozzoli-colchones").
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


def slugificar(nombre: str) -> str:
    return re.sub(r"\s+", "-", normalizar_nombre(nombre) or nombre.lower())


def main():
    parques = leer_csv(DATA / "parques.csv")
    empresas = leer_csv(DATA / "empresas_parque.csv")
    lotes = leer_csv(DATA / "lotes.csv")
    matriculas = leer_csv(DATA / "matriculas.csv")

    if not parques or not empresas:
        raise SystemExit(
            "data/parques.csv o data/empresas_parque.csv vacíos: "
            "correr load_data.py --aplicar primero."
        )

    # ---- SQLite ----
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(ESQUEMA)
    for p in parques:
        con.execute("INSERT INTO parques (id, nombre) VALUES (?,?)", [p["id"], p["nombre"]])
    for e in empresas:
        con.execute(
            """INSERT INTO empresas_parque (id, nombre, cuit, rubro, situacion,
               contacto_nombre, telefono_1, telefono_2, email_1, email_2,
               direccion, pagina_web, instagram, facebook)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [e["id"], e["nombre"], e["cuit"] or None, e["rubro"] or None,
             e["situacion"] or None, e["contacto_nombre"] or None,
             e["telefono_1"] or None, e["telefono_2"] or None,
             e["email_1"] or None, e["email_2"] or None, e["direccion"] or None,
             e["pagina_web"] or None, e["instagram"] or None, e["facebook"] or None],
        )
    for l in lotes:
        con.execute(
            "INSERT INTO lotes (id, parque_id, numero, superficie_m2) VALUES (?,?,?,?)",
            [l["id"], l["parque_id"], l["numero"] or None, l["superficie_m2"] or None],
        )
    for m in matriculas:
        con.execute(
            """INSERT INTO matriculas (id, lote_id, numero_matricula, empresa_id,
               titularidad, estado, observacion) VALUES (?,?,?,?,?,?,?)""",
            [m["id"], m["lote_id"], m["numero_matricula"] or None, m["empresa_id"],
             m["titularidad"] or None, m["estado"] or None, m["observacion"] or None],
        )
    con.commit()
    con.close()
    print(f"OK {DB.name}: {len(parques)} parques, {len(empresas)} empresas, "
          f"{len(lotes)} lotes, {len(matriculas)} matrículas")

    # ---- JSON para el frontend ----
    lotes_por_id = {l["id"]: l for l in lotes}
    matriculas_por_empresa = {}
    for m in matriculas:
        lote = lotes_por_id.get(m["lote_id"], {})
        matriculas_por_empresa.setdefault(m["empresa_id"], []).append({
            "numero_matricula": m["numero_matricula"] or None,
            "numero_lote": lote.get("numero") or None,
            "superficie_m2": lote.get("superficie_m2") or None,
            "titularidad": m["titularidad"] or None,
            "estado": m["estado"] or None,
            "observacion": m["observacion"] or None,
        })

    parques_por_id = {p["id"]: p["nombre"] for p in parques}
    # el parque de una empresa se infiere de sus matrículas -> lotes
    parque_por_empresa = {}
    for m in matriculas:
        lote = lotes_por_id.get(m["lote_id"])
        if lote:
            parque_por_empresa.setdefault(m["empresa_id"], lote["parque_id"])

    slugs_usados = set()
    salida = []
    no_escrituradas = 0
    for e in empresas:
        slug = slugificar(e["nombre"])
        while slug in slugs_usados:
            slug += "-x"
        slugs_usados.add(slug)
        matriculas_emp = matriculas_por_empresa.get(e["id"], [])
        no_escrituradas += sum(1 for m in matriculas_emp if m["estado"] == "no escriturada")
        parque_id = parque_por_empresa.get(e["id"])
        salida.append({
            "id": int(e["id"]),
            "slug": slug,
            "nombre": e["nombre"],
            "cuit": e["cuit"] or None,
            "rubro": e["rubro"] or None,
            "situacion": e["situacion"] or None,
            "contacto": e["contacto_nombre"] or None,
            "telefono_1": e["telefono_1"] or None,
            "telefono_2": e["telefono_2"] or None,
            "email_1": e["email_1"] or None,
            "email_2": e["email_2"] or None,
            "direccion": e["direccion"] or None,
            "web": e["pagina_web"] or None,
            "instagram": e["instagram"] or None,
            "facebook": e["facebook"] or None,
            "parque_id": parque_id,
            "parque": parques_por_id.get(parque_id) if parque_id else None,
            "lotes": matriculas_emp,
        })

    paquete = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parques": [{"id": int(p["id"]), "nombre": p["nombre"]} for p in parques],
        "empresas": salida,
    }
    destino = DATA / "parques.json"
    destino.write_text(json.dumps(paquete, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK {destino.name}: {destino.stat().st_size // 1024} KB")

    # ---- Resumen (Tarea 5: reportar al final del build) ----
    print("\n--- Resumen ---")
    for p in parques:
        emp_ids = {eid for eid, pid in parque_por_empresa.items() if pid == p["id"]}
        print(f"  {p['nombre']}: {len(emp_ids)} empresas")
    print(f"  Matrículas 'no escriturada': {no_escrituradas}")
    cruce_path = DATA / "cruce.json"
    if cruce_path.exists():
        cruce = json.loads(cruce_path.read_text(encoding="utf-8"))
        con_cruce = sum(1 for v in cruce.values() if v.get("en_camaras") and v.get("en_parques"))
        print(f"  Con cruce a cámaras (mismo CUIT en ambos sitios): {con_cruce}")
    else:
        print("  cruce.json no existe todavía — correr cross_link.py para ese dato.")


if __name__ == "__main__":
    main()
