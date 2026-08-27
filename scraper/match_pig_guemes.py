# -*- coding: utf-8 -*-
"""Patch: match del Sheet "Contactos_PI_Güemes_2024" contra el directorio.

No toca el pipeline existente (scrape_*.py / matching.py). Reusa
`normalizar_nombre` / `normalizar_dominio` de common.py para no reinventar
la normalización ya validada contra las 3 cámaras.

Entrada: CSV del Sheet con columnas
  ID, Empresa, Razón Social, Actividad, Rubro, Cuit, email, Teléfono,
  Contacto, Ubicación, Cargo, Pag web, Instagram, LinkedIn
(51 empresas del Parque Industrial Güemes, no vinculadas a CMS/CAPEMISA/UIS).

Salida en data/staging/parque_guemes/:
  - directorio_matches.json (+ .csv): las 51 empresas del Sheet con su nivel
    de match contra data/empresas.csv (444 filas / 378 empresas reales).
  - enriquecimiento.json: para nivel="auto", solo los campos que estaban
    VACÍOS en el directorio y el Sheet sí trae (nunca pisa un dato existente
    — mismo criterio que aplicar_enriquecimiento() en matching.py).
  - nuevas_empresas.json: empresas del Sheet sin match confiable en el
    directorio, pre-formateadas con el esquema de empresas.csv, listas para
    alta MANUAL una vez cruzadas contra los registros escaneados del Parque
    (ver nivel `pendiente_registro_escaneado` — este script NO tiene esos
    registros todavía, así que no puede decidir semi-auto vs unmatched).

Niveles:
  auto                       -> nombre exacto/compacto/dominio ya en el
                                 directorio. Solo actualiza contactos.
  revisar_fuzzy               -> similitud Levenshtein 0.85-0.99: candidato,
                                 NO se fusiona solo (mismo criterio que
                                 candidatos_revision.csv de matching.py).
  pendiente_registro_escaneado -> sin match en el directorio. Falta cruzar
                                 contra los registros escaneados del Parque
                                 para decidir semi-auto (confirma existencia
                                 real) vs unmatched (investigar).
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

    return {"nivel": "pendiente_registro_escaneado", "metodo": None, "similitud": round(mejor_sim, 3) if mejor else 0.0, "match": None}


def armar_enriquecimiento(sheet_emp: dict, match_directorio: dict) -> dict | None:
    campos = {}
    for campo_dir, campo_sheet in CAMPOS_ENRIQUECIBLES:
        valor_dir = (match_directorio.get(campo_dir) or "").strip()
        valor_sheet = sheet_emp.get(campo_sheet) or ""
        if not valor_dir and valor_sheet:
            campos[campo_dir] = valor_sheet
    if not campos:
        return None
    return {
        "empresa_id": int(match_directorio["id"]),
        "nombre_directorio": match_directorio["nombre"],
        "empresa_sheet": sheet_emp["empresa"],
        "campos_a_completar": campos,
        "fuente": "sheet_pig_2024",
    }


def armar_nueva_empresa(sheet_emp: dict, resultado: dict) -> dict:
    return {
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
        "logo_origen": "sheet_pig_2024",
        "contacto_nombre": sheet_emp["contacto"],
        "descripcion": None,
        "ubicacion": "Parque Industrial Güemes, Salta",
        "cuit": sheet_emp["cuit"],
        "rubro_sheet": sheet_emp["rubro"],
        "cargo_contacto": sheet_emp["cargo"],
        "estado_pendiente": "sin_confirmar_contra_registro_escaneado",
        "nota": (
            "Candidato a alta manual (SEMI-AUTO o UNMATCHED según el "
            "registro escaneado del Parque, todavía no cargado en este "
            "match)."
            if resultado["nivel"] == "pendiente_registro_escaneado"
            else f"Match difuso ({resultado['similitud']}) con "
                 f"'{resultado['match']['nombre']}' (id {resultado['match']['id']}) "
                 "— revisar a mano antes de fusionar o dar de alta."
        ),
    }


def main():
    ruta_sheet = Path(sys.argv[1]) if len(sys.argv) > 1 else SALIDA / "contactos_pig_2024.csv"
    if not ruta_sheet.exists():
        raise SystemExit(f"No encuentro el CSV del Sheet: {ruta_sheet}")

    sheet = leer_sheet(ruta_sheet)
    directorio = leer_directorio()
    idx = indexar_directorio(directorio)

    matches, enriquecimientos, nuevas = [], [], []
    conteo = {"auto": 0, "revisar_fuzzy": 0, "pendiente_registro_escaneado": 0}

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
        }
        matches.append(fila_match)

        if r["nivel"] == "auto":
            enr = armar_enriquecimiento(emp, r["match"])
            if enr:
                enriquecimientos.append(enr)
        else:
            nuevas.append(armar_nueva_empresa(emp, r))

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
    print(f"  auto (ya en el directorio):        {conteo['auto']}")
    print(f"  revisar_fuzzy (candidato, no fusiona): {conteo['revisar_fuzzy']}")
    print(f"  pendiente_registro_escaneado:       {conteo['pendiente_registro_escaneado']}")
    print(f"{len(enriquecimientos)} empresas con campos nuevos para completar (nunca pisa datos existentes)")
    print(f"Salida en {SALIDA}/")


if __name__ == "__main__":
    main()
