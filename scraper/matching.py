# -*- coding: utf-8 -*-
"""Matching de entidades + detección de cambios.

Lee data/staging/*.json (salida de los scrapers + enriquecimiento),
fusiona registros que son la misma empresa (cascada de matching) y
diffea contra data/empresas.csv + data/membresias.csv para producir:

- data/empresas.csv      (actualizado, ids estables)
- data/membresias.csv    (actualizado)
- data/cambios.csv       (append: altas / bajas / modificaciones / nuevo_rubro)
- data/candidatos_revision.csv (matches difusos NO fusionados, para revisión)
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from common import DATA, cargar_staging, normalizar_dominio, normalizar_nombre, slugificar

CAMPOS_EMPRESA = [
    "id", "nombre", "nombre_norm", "actividad", "direccion", "telefono",
    "email", "sitio_web", "instagram", "facebook", "linkedin", "logo_url",
    "logo_origen", "contacto_nombre", "descripcion", "ubicacion", "cuit",
]
CAMPOS_MEMBRESIA = ["empresa_id", "camara", "rubro", "url_ficha"]
CAMPOS_CAMBIO = [
    "fecha", "tipo", "empresa_id", "empresa_nombre", "campo",
    "valor_anterior", "valor_nuevo",
]
# Campos cuya modificación se reporta en el changelog
CAMPOS_DIFF = [
    "nombre", "actividad", "direccion", "telefono", "email", "sitio_web",
    "instagram", "contacto_nombre",
]

# Prioridad de fuente al fusionar valores en conflicto (mayor gana)
PRIORIDAD = {"CAPEMISA": 3, "UIS": 2, "CMS": 1}


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nueva = [i]
        for j, cb in enumerate(b, 1):
            nueva.append(min(fila[j] + 1, nueva[-1] + 1, fila[j - 1] + (ca != cb)))
        fila = nueva
    return fila[-1]


def similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    m = max(len(a), len(b))
    return 1.0 - levenshtein(a, b) / m if m else 1.0


class Entidad:
    def __init__(self):
        self.campos = {c: None for c in CAMPOS_EMPRESA if c != "id"}
        self.prioridad = {}        # campo -> prioridad de la fuente que lo seteó
        self.membresias = []       # (camara, rubro, url_ficha)
        self.dominios = set()

    def absorber(self, reg: dict):
        cam = reg["camara"]
        prio = PRIORIDAD.get(cam, 0)
        # nombre: gana el primero visto (CMS corre primero y usa el nombre
        # paraguas del grupo, ej. "AGV Group" en vez de "AGV ... SRL")
        if not self.campos["nombre"]:
            self.campos["nombre"] = reg.get("nombre")
        mapeo = {
            "actividad": reg.get("actividad"),
            "direccion": reg.get("direccion"),
            "telefono": reg.get("telefono"),
            "email": reg.get("email"),
            "sitio_web": reg.get("sitio_web"),
            "contacto_nombre": reg.get("contacto_nombre"),
            "descripcion": reg.get("descripcion"),
            "ubicacion": reg.get("ubicacion"),
        }
        for campo, valor in mapeo.items():
            if not valor:
                continue
            if self.campos.get(campo) is None or prio > self.prioridad.get(campo, -1):
                self.campos[campo] = valor
                self.prioridad[campo] = prio
        # logo: cualquier logo real le gana a un placeholder
        logo = reg.get("logo_url")
        if logo and not reg.get("logo_placeholder"):
            if self.campos["logo_url"] is None or self.campos.get("logo_origen") == "placeholder":
                self.campos["logo_url"] = logo
                self.campos["logo_origen"] = "camara"
        elif logo and self.campos["logo_url"] is None:
            self.campos["logo_url"] = logo
            self.campos["logo_origen"] = "placeholder"
        memb = (cam, reg.get("rubro"), reg.get("url_ficha"))
        if (cam, reg.get("rubro")) not in [(c, r) for c, r, _ in self.membresias]:
            self.membresias.append(memb)
        dom = normalizar_dominio(reg.get("sitio_web") or "")
        if dom:
            self.dominios.add(dom)
        self.campos["nombre_norm"] = normalizar_nombre(self.campos["nombre"])


def construir_entidades(registros: list) -> tuple[list, list]:
    """Cascada: 1) nombre_norm exacto  2) dominio  3) fuzzy  4) representante -> solo log."""
    entidades = []
    por_norm = {}
    por_compacto = {}  # norm sin espacios: matchea "co pro tab" con "coprotab"
    por_dominio = {}
    por_contacto = {}  # contacto_norm -> list[Entidad]
    candidatos = []
    pares_vistos = set()  # evita duplicar el mismo par en candidatos

    for reg in registros:
        if not reg.get("nombre"):
            continue
        norm = normalizar_nombre(reg["nombre"])
        compacto = norm.replace(" ", "")
        dom = normalizar_dominio(reg.get("sitio_web") or "")
        ent = (
            por_norm.get(norm)
            or por_compacto.get(compacto)
            or (por_dominio.get(dom) if dom else None)
        )
        if ent is None:
            # regla 3: similitud Levenshtein >= 0.85 -> loggear, NO fusionar
            for otra_norm, otra_ent in por_norm.items():
                s = similitud(norm, otra_norm)
                if 0.85 <= s < 1.0:
                    par = tuple(sorted([norm, otra_norm]))
                    if par not in pares_vistos:
                        pares_vistos.add(par)
                        candidatos.append({
                            "nombre_a": reg["nombre"],
                            "nombre_b": otra_ent.campos["nombre"],
                            "similitud": round(s, 3),
                            "regla": "levenshtein",
                        })
            # regla 4: representante coincidente + rubro coincidente -> candidato
            contacto_norm = normalizar_nombre(reg.get("contacto_nombre") or "")
            rubro_reg = (reg.get("camara") or "", reg.get("rubro") or "")
            if contacto_norm and len(contacto_norm) > 3:
                for otra_ent in por_contacto.get(contacto_norm, []):
                    rubros_otra = {(m[0], m[1]) for m in otra_ent.membresias}
                    if rubro_reg in rubros_otra or reg.get("camara") in {m[0] for m in otra_ent.membresias}:
                        par = tuple(sorted([norm, otra_ent.campos["nombre_norm"] or ""]))
                        if par not in pares_vistos:
                            pares_vistos.add(par)
                            candidatos.append({
                                "nombre_a": reg["nombre"],
                                "nombre_b": otra_ent.campos["nombre"],
                                "similitud": 0.0,
                                "regla": f"representante:{contacto_norm}",
                            })
            ent = Entidad()
            entidades.append(ent)
        ent.absorber(reg)
        por_norm[norm] = ent
        por_norm[ent.campos["nombre_norm"]] = ent
        por_compacto[compacto] = ent
        por_compacto[ent.campos["nombre_norm"].replace(" ", "")] = ent
        for d in ent.dominios:
            por_dominio[d] = ent
        # indexar por representante para regla 4
        contacto_norm = normalizar_nombre(ent.campos.get("contacto_nombre") or "")
        if contacto_norm and len(contacto_norm) > 3:
            if ent not in por_contacto.setdefault(contacto_norm, []):
                por_contacto[contacto_norm].append(ent)
    return entidades, candidatos


def aplicar_enriquecimiento(entidades: list):
    """Merge de data/staging/enriquecimiento.json (keyed por dominio)."""
    enr = cargar_staging("enriquecimiento.json")
    if not enr:
        return
    por_dominio = enr if isinstance(enr, dict) else {}
    for ent in entidades:
        for dom in ent.dominios:
            info = por_dominio.get(dom)
            if not info:
                continue
            for campo in ("email", "telefono", "instagram", "facebook", "linkedin"):
                if info.get(campo) and not ent.campos.get(campo):
                    ent.campos[campo] = info[campo]
            # logo del sitio oficial reemplaza placeholders y suma calidad
            if info.get("logo_url"):
                if ent.campos.get("logo_origen") in (None, "placeholder") or info.get("logo_es_svg"):
                    ent.campos["logo_url"] = info["logo_url"]
                    ent.campos["logo_origen"] = "sitio_oficial"


def leer_csv(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv(path: Path, filas: list, campos: list):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({c: ("" if fila.get(c) is None else fila.get(c)) for c in campos})


def main():
    registros = (
        cargar_staging("cms.json")
        + cargar_staging("capemisa.json")
        + cargar_staging("uis.json")
    )
    if not registros:
        raise SystemExit("Sin staging: correr los scrapers primero.")

    entidades, candidatos = construir_entidades(registros)
    aplicar_enriquecimiento(entidades)
    print(f"{len(registros)} registros -> {len(entidades)} entidades")

    # ---- diff contra estado anterior ----
    previas = {e["nombre_norm"]: e for e in leer_csv(DATA / "empresas.csv")}
    memb_previas = leer_csv(DATA / "membresias.csv")
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cambios = []

    max_id = max((int(e["id"]) for e in previas.values()), default=0)
    filas_empresas, filas_membresias = [], []
    vistas = set()

    for ent in entidades:
        norm = ent.campos["nombre_norm"]
        vistas.add(norm)
        previa = previas.get(norm)
        if previa is None:
            max_id += 1
            eid = max_id
            cambios.append({
                "fecha": ahora, "tipo": "alta", "empresa_id": eid,
                "empresa_nombre": ent.campos["nombre"], "campo": "",
                "valor_anterior": "", "valor_nuevo": "",
            })
        else:
            eid = int(previa["id"])
            for campo in CAMPOS_DIFF:
                viejo = (previa.get(campo) or "").strip()
                nuevo = (ent.campos.get(campo) or "").strip()
                if viejo and nuevo and viejo != nuevo:
                    cambios.append({
                        "fecha": ahora, "tipo": "modificacion", "empresa_id": eid,
                        "empresa_nombre": ent.campos["nombre"], "campo": campo,
                        "valor_anterior": viejo, "valor_nuevo": nuevo,
                    })
            rubros_previos = {
                (m["camara"], m["rubro"]) for m in memb_previas
                if m["empresa_id"] == str(eid)
            }
            for cam, rubro, _ in ent.membresias:
                if rubros_previos and (cam, rubro) not in rubros_previos:
                    cambios.append({
                        "fecha": ahora, "tipo": "nuevo_rubro", "empresa_id": eid,
                        "empresa_nombre": ent.campos["nombre"], "campo": "membresia",
                        "valor_anterior": "", "valor_nuevo": f"{cam} / {rubro or ''}",
                    })
        fila = {"id": eid, **ent.campos}
        filas_empresas.append(fila)
        for cam, rubro, url in ent.membresias:
            filas_membresias.append({
                "empresa_id": eid, "camara": cam, "rubro": rubro or "", "url_ficha": url or "",
            })

    for norm, previa in previas.items():
        if norm not in vistas:
            cambios.append({
                "fecha": ahora, "tipo": "baja", "empresa_id": previa["id"],
                "empresa_nombre": previa["nombre"], "campo": "",
                "valor_anterior": previa["nombre"], "valor_nuevo": "",
            })

    filas_empresas.sort(key=lambda f: normalizar_nombre(f["nombre"]))
    escribir_csv(DATA / "empresas.csv", filas_empresas, CAMPOS_EMPRESA)
    escribir_csv(DATA / "membresias.csv", filas_membresias, CAMPOS_MEMBRESIA)

    historial = leer_csv(DATA / "cambios.csv")
    primera_corrida = not previas
    if primera_corrida:
        # la carga inicial no es "novedad": no inflar el changelog con N altas
        cambios = []
    escribir_csv(DATA / "cambios.csv", historial + cambios, CAMPOS_CAMBIO)

    if candidatos:
        escribir_csv(
            DATA / "candidatos_revision.csv", candidatos,
            ["nombre_a", "nombre_b", "similitud", "regla"],
        )
        print(f"ATENCION: {len(candidatos)} candidatos difusos en candidatos_revision.csv")

    resumen = {}
    for c in cambios:
        resumen[c["tipo"]] = resumen.get(c["tipo"], 0) + 1
    (DATA / "resumen_run.json").write_text(
        json.dumps({"fecha": ahora, "cambios": resumen}, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Cambios: {resumen or 'ninguno'}")


if __name__ == "__main__":
    main()
