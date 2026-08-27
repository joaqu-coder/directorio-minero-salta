# -*- coding: utf-8 -*-
"""Patch: match del Sheet "Contactos_PI_Güemes_2024" contra el directorio.

No toca el pipeline existente (scrape_*.py / matching.py). Reusa
`normalizar_nombre` / `normalizar_dominio` de common.py para no reinventar
la normalización ya validada contra las 3 cámaras.

Entrada: CSV del Sheet con columnas
  ID, Empresa, Razón Social, Actividad, Rubro, Cuit, email, Teléfono,
  Contacto, Ubicación, Cargo, Pag web, Instagram, LinkedIn
(52 empresas del Parque Industrial Güemes, no vinculadas a CMS/CAPEMISA/UIS).
El Sheet es la fuente completa — no hay un segundo registro (escaneado o de
otro tipo) contra el cual confirmar existencia, así que toda empresa del
Sheet sin match en el directorio pasa directo a "nueva" (candidata a alta).

Salida en data/staging/parque_guemes/:
  - directorio_matches.json (+ .csv): las 52 empresas del Sheet con su nivel
    de match contra data/empresas.csv (444 filas / 378 empresas reales).
  - enriquecimiento.json: para nivel="auto", solo los campos que estaban
    VACÍOS en el directorio y el Sheet sí trae (nunca pisa un dato existente
    — mismo criterio que aplicar_enriquecimiento() en matching.py).
  - nuevas_empresas.json: empresas del Sheet sin match confiable en el
    directorio, pre-formateadas con el esquema de empresas.csv. Sin logo
    (pendiente, no viene en el Sheet).

Niveles:
  auto          -> nombre exacto/compacto/dominio ya en el directorio. Solo
                    actualiza contactos vacíos + agrega la membresía
                    "Parque Industrial Güemes" (dato nuevo: confirma que
                    esa empresa YA conocida también tiene planta en el PIG).
  revisar_fuzzy -> match ambiguo (dominio compartido por un grupo con razón
                    social distinta, o nombre 0.85-0.99 de similar) — NO se
                    fusiona solo, mismo criterio que candidatos_revision.csv
                    de matching.py. Requiere decisión humana, independiente
                    de si hay o no un registro externo para confirmarlo.
  nueva         -> sin match en el directorio. Candidata a alta directa con
                    --aplicar.

--aplicar escribe de verdad en data/empresas.csv, data/membresias.csv y
data/cambios.csv (backup .bak antes de tocar cada uno). Sin el flag, el
script solo genera los JSON/CSV de staging para revisión.
"""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

# No importamos common.py: arrastra `from scrapling.fetchers import Fetcher`
# (curl_cffi/playwright) solo para usar dos funciones puras de string. Este
# patch no hace fetch de nada, así que copiamos normalizar_nombre/
# normalizar_dominio tal cual están en common.py (no se reinventa la lógica,
# se evita la dependencia de red de un script que no la necesita).

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
SALIDA = DATA / "staging" / "parque_guemes"

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
    while previo != s:
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

CAMPOS_ENRIQUECIBLES = [
    ("email", "email"),
    ("telefono", "telefono"),
    ("contacto_nombre", "contacto"),
    ("sitio_web", "pag_web"),
    ("instagram", "instagram"),
    ("linkedin", "linkedin"),
    ("cuit", "cuit"),
]

CAMPOS_NUEVA_EMPRESA = [
    "id", "nombre", "nombre_norm", "actividad", "direccion", "telefono",
    "email", "sitio_web", "instagram", "facebook", "linkedin", "logo_url",
    "logo_origen", "contacto_nombre", "descripcion", "ubicacion", "cuit",
]


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


def limpiar(valor: str) -> str:
    if not valor:
        return ""
    v = valor.strip()
    if v.lower() in ("no disponible", "sin cuit", "sin actividad", ""):
        return ""
    return v.replace("\n", " ").strip()


def limpiar_multivalor(valor: str) -> str:
    """Como limpiar(), pero para campos donde el Sheet a veces mete más de
    un dato separado por "/" o salto de línea (dos emails, dos teléfonos,
    dos contactos): nos quedamos con el primero. Divide ANTES de que
    limpiar() colapse los saltos de línea a espacio (si no, no queda nada
    para partir). NO usar en URLs (el "/" es parte de la URL) ni en
    ubicación (ej. "PARCELA 15/16")."""
    if not valor or valor.strip().lower() in ("no disponible", "sin cuit", "sin actividad"):
        return ""
    primero = re.split(r"[\n/]", valor.strip())[0]
    return limpiar(primero)


def leer_sheet(ruta: Path) -> list:
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = list(csv.reader(f))
    # 2 filas en blanco + 1 fila de encabezado antes de los datos reales
    encabezado_idx = next(
        i for i, fila in enumerate(filas) if fila and fila[0].strip() == "ID"
    )
    claves = [c.strip() for c in filas[encabezado_idx]]
    empresas = []
    for fila in filas[encabezado_idx + 1:]:
        if not fila or not fila[0].strip():
            continue
        reg = dict(zip(claves, fila))
        empresa = limpiar(reg.get("Empresa", ""))
        if not empresa:
            continue
        razon_social = limpiar(reg.get("Razón Social", ""))
        # El Sheet separa "Empresa" y "Razón Social" (ej. "FMF Argentina" +
        # "S.R.L."); el directorio los trae concatenados ("FMF ARGENTINA
        # S.R.L."). Armamos el nombre completo para que la normalización
        # (que recorta formas legales) compare manzanas con manzanas.
        nombre_completo = empresa
        if razon_social and razon_social != "Otra":
            # Comparación solo alfanumérica: "FMF Composite S.R.L" ya
            # termina en la forma legal aunque "SRL" (razón social) no
            # tenga los puntos — sin este chequeo quedaba
            # "FMF Composite S.R.L SRL" duplicado.
            sola = re.sub(r"[^a-z0-9]", "", empresa.lower())
            rs = re.sub(r"[^a-z0-9]", "", razon_social.lower())
            if not sola.endswith(rs):
                nombre_completo = f"{empresa} {razon_social}"
        empresas.append({
            "sheet_id": reg.get("ID", "").strip(),
            "empresa": empresa,
            "razon_social": razon_social,
            "nombre_completo": nombre_completo,
            "actividad": limpiar(reg.get("Actividad", "")),
            "rubro": limpiar(reg.get("Rubro", "")),
            "cuit": limpiar(reg.get("Cuit", "")),
            "email": limpiar_multivalor(reg.get("email", "")),
            "telefono": limpiar_multivalor(reg.get("Teléfono", "")),
            "contacto": limpiar_multivalor(reg.get("Contacto", "")),
            "ubicacion": limpiar(reg.get("Ubicación", "")) or "Parque Industrial Güemes, Salta",
            "cargo": limpiar(reg.get("Cargo", "")),
            "pag_web": limpiar(reg.get("Pag web", "")),
            "instagram": limpiar(reg.get("Instagram", "")),
            "linkedin": limpiar(reg.get("LinkedIn", "")),
        })
    return empresas


def leer_directorio() -> list:
    with (DATA / "empresas.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def indexar_directorio(empresas: list) -> dict:
    idx = {"norm": {}, "compacto": {}, "dominio": {}, "todas": empresas}
    for emp in empresas:
        norm = emp.get("nombre_norm") or normalizar_nombre(emp["nombre"])
        idx["norm"].setdefault(norm, emp)
        idx["compacto"].setdefault(norm.replace(" ", ""), emp)
        dom = normalizar_dominio(emp.get("sitio_web") or "")
        if dom:
            idx["dominio"].setdefault(dom, emp)
    return idx


def matchear(sheet_emp: dict, idx: dict) -> dict:
    norm = normalizar_nombre(sheet_emp["nombre_completo"])
    compacto = norm.replace(" ", "")
    dom = normalizar_dominio(sheet_emp.get("pag_web") or "")

    if norm in idx["norm"]:
        return {"nivel": "auto", "metodo": "nombre_exacto", "similitud": 1.0, "match": idx["norm"][norm]}
    if compacto in idx["compacto"]:
        return {"nivel": "auto", "metodo": "nombre_compacto", "similitud": 1.0, "match": idx["compacto"][compacto]}
    if dom and dom in idx["dominio"]:
        candidato = idx["dominio"][dom]
        # Un dominio compartido no basta: un grupo empresarial (ej. FMF)
        # puede tener varias razones sociales bajo el mismo sitio ("FMF
        # Composite S.R.L." y "FMF Argentina S.R.L." comparten fmfsa.com y
        # son empresas DISTINTAS con CUIT distinto). Si el nombre no se
        # parece nada, no es AUTO — es candidato a revisión manual, mismo
        # criterio conservador que el resto del repo ("ante la duda, no
        # colapsar").
        sim_nombre = similitud(norm, normalizar_nombre(candidato["nombre"]))
        if sim_nombre >= 0.5:
            return {"nivel": "auto", "metodo": "dominio", "similitud": 1.0, "match": candidato}
        return {
            "nivel": "revisar_fuzzy", "metodo": "dominio_nombre_distinto",
            "similitud": round(sim_nombre, 3), "match": candidato,
        }

    mejor = None
    mejor_sim = 0.0
    for otra_norm, emp in idx["norm"].items():
        s = similitud(norm, otra_norm)
        if s > mejor_sim:
            mejor_sim, mejor = s, emp
    if mejor is not None and 0.85 <= mejor_sim < 1.0:
        return {"nivel": "revisar_fuzzy", "metodo": "levenshtein", "similitud": round(mejor_sim, 3), "match": mejor}

    return {"nivel": "nueva", "metodo": None, "similitud": round(mejor_sim, 3) if mejor else 0.0, "match": None}


def armar_enriquecimiento(sheet_emp: dict, match_directorio: dict, resultado: dict) -> dict | None:
    campos = {}
    for campo_dir, campo_sheet in CAMPOS_ENRIQUECIBLES:
        valor_dir = (match_directorio.get(campo_dir) or "").strip()
        valor_sheet = sheet_emp.get(campo_sheet) or ""
        if not valor_dir and valor_sheet:
            campos[campo_dir] = valor_sheet
    if not campos:
        return None
    enr = {
        "empresa_id": int(match_directorio["id"]),
        "nombre_directorio": match_directorio["nombre"],
        "empresa_sheet": sheet_emp["empresa"],
        "campos_a_completar": campos,
        "rubro_sheet": sheet_emp["rubro"],
        "fuente": "sheet_pig_2024",
        "nivel_match": resultado["nivel"],
    }
    if resultado["nivel"] == "revisar_fuzzy":
        # Match ambiguo (dominio compartido por un grupo con razón social
        # distinta, o nombre 0.85-0.99 de similar): NO se fusiona el nombre
        # ni se sobrescribe nada — solo se completan campos que ya estaban
        # vacíos, a pedido explícito del usuario ("comparte la información
        # que sea complementaria").
        enr["nota"] = (
            f"Match ambiguo ({resultado['metodo']}, similitud "
            f"{resultado['similitud']}) con '{sheet_emp['nombre_completo']}' "
            "— se completaron solo los campos vacíos, el nombre y la "
            "actividad del directorio no se tocaron."
        )
    return enr


def armar_nueva_empresa(sheet_emp: dict) -> dict:
    return {
        "nivel": "nueva",
        "id": None,
        "nombre": sheet_emp["nombre_completo"],
        "nombre_norm": normalizar_nombre(sheet_emp["nombre_completo"]),
        "actividad": sheet_emp["actividad"],
        "direccion": sheet_emp["ubicacion"],
        "telefono": sheet_emp["telefono"],
        "email": sheet_emp["email"],
        "sitio_web": sheet_emp["pag_web"],
        "instagram": sheet_emp["instagram"],
        "facebook": "",
        "linkedin": sheet_emp["linkedin"],
        "logo_url": None,
        "logo_origen": None,
        "contacto_nombre": sheet_emp["contacto"],
        "descripcion": None,
        "ubicacion": "Parque Industrial Güemes, Salta",
        "cuit": sheet_emp["cuit"],
        "rubro_sheet": sheet_emp["rubro"],
        "cargo_contacto": sheet_emp["cargo"],
        "logo_pendiente": True,
        "nota": "Candidata a alta directa (con --aplicar). Logo pendiente: el Sheet no trae uno.",
    }


CAMARA_PIG = "Parque Industrial Güemes"

CAMPOS_MEMBRESIA = ["empresa_id", "camara", "rubro", "url_ficha"]
CAMPOS_CAMBIO = [
    "fecha", "tipo", "empresa_id", "empresa_nombre", "campo",
    "valor_anterior", "valor_nuevo",
]


def leer_csv_generico(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv_generico(path: Path, filas: list, campos: list):
    path.with_suffix(path.suffix + ".bak").write_bytes(path.read_bytes()) if path.exists() else None
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({c: ("" if fila.get(c) is None else fila.get(c)) for c in campos})


def aplicar(matches_completar: list, enriquecimientos: list, nuevas: list, directorio: list):
    """matches_completar: matches nivel "auto" o "revisar_fuzzy" (con o sin
    campos para completar) — cada uno suma la membresía "Parque Industrial
    Güemes" y, si había algo vacío, lo completa. NUNCA renombra ni fusiona
    el registro existente — eso es justo la diferencia entre auto y
    revisar_fuzzy con la nueva empresa que sí se da de alta aparte."""
    import datetime as _dt

    campos_empresa = list(directorio[0].keys()) if directorio else CAMPOS_NUEVA_EMPRESA
    ahora = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    membresias = leer_csv_generico(DATA / "membresias.csv")
    cambios = leer_csv_generico(DATA / "cambios.csv")
    membresias_existentes = {(m["empresa_id"], m["camara"]) for m in membresias}

    por_id = {e["id"]: e for e in directorio}

    # Dos filas del Sheet pueden apuntar al MISMO empresa_id (ej. FMF
    # Composite y FMF Argentina comparten el registro "FMF ARGENTINA S.R.L."
    # en el directorio) y proponer valores DISTINTOS para el mismo campo
    # vacío (CUIT de una razón social vs. la otra). Agrupamos antes de
    # escribir: si dos fuentes proponen el mismo campo con valores
    # distintos, no se aplica ninguno — se solapan datos de dos entidades
    # y "cuál gana" no es una decisión que el script deba tomar solo.
    propuestas = {}  # empresa_id -> {campo: {valor: [origen, ...]}}
    for enr in enriquecimientos:
        eid = enr["empresa_id"]
        for campo, valor in enr["campos_a_completar"].items():
            propuestas.setdefault(eid, {}).setdefault(campo, {}).setdefault(valor, []).append(enr["empresa_sheet"])

    conflictos = []
    conflictos_vistos = set()
    for m in matches_completar:
        eid = m["empresa_id_directorio"]
        fila = por_id.get(str(eid))
        if fila is None:
            continue
        for campo, valores in propuestas.get(eid, {}).items():
            if fila.get(campo):
                continue  # ya se completó (otra fila del Sheet coincidía) o ya tenía dato
            if len(valores) > 1:
                clave_conflicto = (eid, campo)
                if clave_conflicto not in conflictos_vistos:
                    conflictos_vistos.add(clave_conflicto)
                    conflictos.append({"empresa_id": eid, "campo": campo, "propuestas": valores})
                continue
            (valor, origenes), = valores.items()
            viejo = fila.get(campo) or ""
            fila[campo] = valor
            cambios.append({
                "fecha": ahora, "tipo": "modificacion", "empresa_id": eid,
                "empresa_nombre": fila["nombre"], "campo": campo,
                "valor_anterior": viejo, "valor_nuevo": valor,
            })
        clave = (str(eid), CAMARA_PIG)
        if clave not in membresias_existentes:
            membresias_existentes.add(clave)
            membresias.append({
                "empresa_id": eid, "camara": CAMARA_PIG,
                "rubro": m.get("rubro_sheet") or "", "url_ficha": "",
            })

    max_id = max((int(e["id"]) for e in directorio), default=0)
    for nueva in nuevas:
        if nueva.get("nivel") != "nueva":
            continue  # revisar_fuzzy: nunca se da de alta sola
        max_id += 1
        fila = {c: nueva.get(c) for c in campos_empresa}
        fila["id"] = max_id
        directorio.append(fila)
        cambios.append({
            "fecha": ahora, "tipo": "alta", "empresa_id": max_id,
            "empresa_nombre": nueva["nombre"], "campo": "",
            "valor_anterior": "", "valor_nuevo": "",
        })
        membresias.append({
            "empresa_id": max_id, "camara": CAMARA_PIG,
            "rubro": nueva.get("rubro_sheet") or "", "url_ficha": "",
        })

    escribir_csv_generico(DATA / "empresas.csv", directorio, campos_empresa)
    escribir_csv_generico(DATA / "membresias.csv", membresias, CAMPOS_MEMBRESIA)
    escribir_csv_generico(DATA / "cambios.csv", cambios, CAMPOS_CAMBIO)
    altas = sum(1 for n in nuevas if n.get("nivel") == "nueva")
    print(f"Aplicado: {len(matches_completar)} empresas con membresía PIG agregada "
          f"({len(enriquecimientos)} con contactos completados), {altas} altas nuevas.")
    if conflictos:
        print(f"CONFLICTOS ({len(conflictos)}) — dos filas del Sheet proponen valores "
              "distintos para el mismo campo vacío, no se aplicó ninguno:")
        for c in conflictos:
            print(f"  empresa_id={c['empresa_id']} campo={c['campo']}: {dict(c['propuestas'])}")
    print("Backups .bak junto a cada CSV. Falta correr build_db.py para refrescar directorio.db/empresas.json.")


def main():
    aplicar_de_verdad = "--aplicar" in sys.argv
    args_posicionales = [a for a in sys.argv[1:] if not a.startswith("--")]
    ruta_sheet = Path(args_posicionales[0]) if args_posicionales else SALIDA / "contactos_pig_2024.csv"
    if not ruta_sheet.exists():
        raise SystemExit(f"No encuentro el CSV del Sheet: {ruta_sheet}")

    sheet = leer_sheet(ruta_sheet)
    directorio = leer_directorio()
    idx = indexar_directorio(directorio)

    matches, enriquecimientos, nuevas = [], [], []
    conteo = {"auto": 0, "revisar_fuzzy": 0, "nueva": 0}

    for emp in sheet:
        r = matchear(emp, idx)
        conteo[r["nivel"]] += 1
        fila_match = {
            "sheet_id": emp["sheet_id"],
            "empresa_sheet": emp["empresa"],
            "nombre_completo_sheet": emp["nombre_completo"],
            "nivel": r["nivel"],
            "metodo_match": r["metodo"],
            "similitud": r["similitud"],
            "empresa_id_directorio": int(r["match"]["id"]) if r["match"] else None,
            "nombre_directorio": r["match"]["nombre"] if r["match"] else None,
            "rubro_sheet": emp["rubro"],
        }
        matches.append(fila_match)

        if r["nivel"] in ("auto", "revisar_fuzzy"):
            enr = armar_enriquecimiento(emp, r["match"], r)
            if enr:
                enriquecimientos.append(enr)
        else:
            nuevas.append(armar_nueva_empresa(emp))

    SALIDA.mkdir(parents=True, exist_ok=True)

    (SALIDA / "directorio_matches.json").write_text(
        json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (SALIDA / "directorio_matches.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(matches[0].keys()))
        w.writeheader()
        w.writerows(matches)

    (SALIDA / "enriquecimiento.json").write_text(
        json.dumps(enriquecimientos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (SALIDA / "nuevas_empresas.json").write_text(
        json.dumps(nuevas, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{len(sheet)} empresas del Sheet procesadas")
    print(f"  auto (ya en el directorio):    {conteo['auto']}")
    print(f"  revisar_fuzzy (no se fusiona): {conteo['revisar_fuzzy']}")
    print(f"  nueva (candidata a alta):      {conteo['nueva']}")
    print(f"{len(enriquecimientos)} empresas con campos nuevos para completar (nunca pisa datos existentes)")
    print(f"Salida en {SALIDA}/")

    if aplicar_de_verdad:
        # auto + revisar_fuzzy: ambos suman membresía PIG y completan campos
        # vacíos. revisar_fuzzy nunca se renombra ni se da de alta aparte.
        matches_completar = [m for m in matches if m["nivel"] in ("auto", "revisar_fuzzy")]
        aplicar(matches_completar, enriquecimientos, nuevas, directorio)


if __name__ == "__main__":
    main()
