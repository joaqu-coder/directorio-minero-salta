# -*- coding: utf-8 -*-
"""CSV (source of truth) -> SQLite (directorio.db) + JSON estático (empresas.json)."""
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from common import DATA, RAIZ, normalizar_nombre, slugificar

DB = RAIZ / "directorio.db"

ESQUEMA = """
CREATE TABLE empresas (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_norm TEXT NOT NULL,
    actividad TEXT,
    direccion TEXT,
    telefono TEXT,
    email TEXT,
    sitio_web TEXT,
    instagram TEXT,
    facebook TEXT,
    linkedin TEXT,
    logo_url TEXT,
    logo_origen TEXT,
    contacto_nombre TEXT,
    descripcion TEXT,
    ubicacion TEXT,
    cuit TEXT,
    creado_en TEXT DEFAULT (datetime('now')),
    actualizado_en TEXT
);
CREATE UNIQUE INDEX idx_empresas_norm ON empresas(nombre_norm);

CREATE TABLE membresias (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id),
    camara TEXT NOT NULL,
    rubro TEXT,
    url_ficha TEXT,
    UNIQUE(empresa_id, camara, rubro)
);

CREATE TABLE cambios (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id),
    fecha TEXT DEFAULT (datetime('now')),
    tipo TEXT,
    campo TEXT,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    visto INTEGER DEFAULT 0
);

CREATE TABLE representantes (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id),
    nombre TEXT,
    nombre_norm TEXT
);
"""


def leer_csv(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    empresas = leer_csv(DATA / "empresas.csv")
    membresias = leer_csv(DATA / "membresias.csv")
    cambios = leer_csv(DATA / "cambios.csv")
    if not empresas:
        raise SystemExit("data/empresas.csv vacío: correr matching.py primero.")

    # ---- SQLite ----
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(ESQUEMA)
    for e in empresas:
        con.execute(
            """INSERT INTO empresas (id, nombre, nombre_norm, actividad, direccion,
               telefono, email, sitio_web, instagram, facebook, linkedin, logo_url,
               logo_origen, contacto_nombre, descripcion, ubicacion, cuit, actualizado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
            [e["id"], e["nombre"], e["nombre_norm"], e["actividad"] or None,
             e["direccion"] or None, e["telefono"] or None, e["email"] or None,
             e["sitio_web"] or None, e["instagram"] or None, e["facebook"] or None,
             e["linkedin"] or None, e["logo_url"] or None, e["logo_origen"] or None,
             e["contacto_nombre"] or None, e.get("descripcion") or None,
             e.get("ubicacion") or None, e.get("cuit") or None],
        )
        if e["contacto_nombre"]:
            con.execute(
                "INSERT INTO representantes (empresa_id, nombre, nombre_norm) VALUES (?,?,?)",
                [e["id"], e["contacto_nombre"], normalizar_nombre(e["contacto_nombre"])],
            )
    for m in membresias:
        con.execute(
            "INSERT OR IGNORE INTO membresias (empresa_id, camara, rubro, url_ficha) VALUES (?,?,?,?)",
            [m["empresa_id"], m["camara"], m["rubro"] or None, m["url_ficha"] or None],
        )
    for c in cambios:
        con.execute(
            """INSERT INTO cambios (empresa_id, fecha, tipo, campo, valor_anterior, valor_nuevo)
               VALUES (?,?,?,?,?,?)""",
            [c["empresa_id"] or None, c["fecha"], c["tipo"], c["campo"] or None,
             c["valor_anterior"] or None, c["valor_nuevo"] or None],
        )
    con.commit()
    con.close()
    print(f"OK {DB.name}: {len(empresas)} empresas, {len(membresias)} membresías")

    # ---- JSON para el frontend ----
    memb_por_empresa = {}
    for m in membresias:
        memb_por_empresa.setdefault(m["empresa_id"], []).append({
            "camara": m["camara"],
            "rubro": m["rubro"] or None,
            "url": m["url_ficha"] or None,
        })

    slugs_usados = set()
    salida = []
    for e in empresas:
        slug = slugificar(e["nombre"])
        while slug in slugs_usados:
            slug += "-x"
        slugs_usados.add(slug)
        salida.append({
            "id": int(e["id"]),
            "slug": slug,
            "nombre": e["nombre"],
            "actividad": e["actividad"] or None,
            "direccion": e["direccion"] or None,
            "telefono": e["telefono"] or None,
            "email": e["email"] or None,
            "web": e["sitio_web"] or None,
            "instagram": e["instagram"] or None,
            "facebook": e["facebook"] or None,
            "linkedin": e["linkedin"] or None,
            "logo": e["logo_url"] or None,
            "logo_origen": e["logo_origen"] or None,
            "contacto": e["contacto_nombre"] or None,
            "descripcion": e.get("descripcion") or None,
            "ubicacion": e.get("ubicacion") or None,
            "membresias": memb_por_empresa.get(e["id"], []),
        })

    cambios_json = [{
        "fecha": c["fecha"],
        "tipo": c["tipo"],
        "empresa_id": int(c["empresa_id"]) if c["empresa_id"] else None,
        "empresa": c["empresa_nombre"],
        "campo": c["campo"] or None,
        "antes": c["valor_anterior"] or None,
        "despues": c["valor_nuevo"] or None,
    } for c in cambios]
    cambios_json.sort(key=lambda c: c["fecha"], reverse=True)

    paquete = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "empresas": salida,
        "cambios": cambios_json[:200],
    }
    destino = DATA / "empresas.json"
    destino.write_text(json.dumps(paquete, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK {destino.name}: {destino.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
