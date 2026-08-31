# -*- coding: utf-8 -*-
"""Normaliza las 2 fuentes de datos de parques industriales al esquema
común de /parques (parques / lotes / matriculas / empresas_parque).

Fuentes:
  data/raw/pi_guemes.csv  — export CSV del Google Sheet "Contactos PI
                             Güemes 2024" (52 empresas, solo contactos —
                             sin lote/matrícula/superficie/titularidad).
                             Mismo formato que ya procesaba
                             scraper/match_pig_guemes.py.
  data/raw/pi_salta.csv   — export CSV de la hoja Resumen_Empresas de
                             PI_Salta_Normalizado.xlsx (130 empresas).
                             Columnas: Empresa, CUIT, Lotes, Matriculas,
                             Superficie_Total, Titularidad, Ocupante_Actual,
                             Rubro, Situacion, Contacto, Direccion,
                             Telefono_1, Telefono_2, Email_1, Email_2,
                             Presencia_Digital ("web | instagram |
                             facebook", siempre 3 partes), Estado_Matrícula,
                             Observación. "Lotes" es 1 solo número de lote
                             por fila (no una lista); "Matriculas" sí puede
                             traer varias separadas por coma — todas cuelgan
                             del mismo lote (confirmado con CERAMICA
                             ALBERDI: Lotes=1, 3 matrículas). "Titularidad"
                             puede traer varios valores separados por "|"
                             (copropietarios) que NO siempre alinean 1:1
                             con la cantidad de matrículas (27/130 filas
                             desalinean) — no se intenta repartir por
                             matrícula, se guarda el string completo tal
                             cual en cada matrícula del lote.

Reglas de negocio (no reinterpretar):
  - Todas las empresas de un parque son propietarias (escrituradas o no).
    No existe "inquilino puro alquilando al ente": no se arma tabla de
    ocupaciones. Los casos con Situacion="Alquilada" (empresa propietaria
    que alquila a OTRA empresa del parque) quedan fuera de scope.
  - estado="no escriturada" solo dice que la matrícula sigue a nombre del
    Ente o de una persona física — nunca se inventa el motivo (trámite,
    pendiente, rechazo) si la fuente no lo dice.
  - HIELOS ARTUR y ALIMENTOS TECNOLOGICOS ya vienen fusionados en 1 fila
    en la fuente de Salta — no se vuelven a separar. ZOZZOLI son 3 filas
    = 3 empresas reales distintas (Colchones/Muebles/Sillas) — no se
    fusionan por compartir CUIT.
  - Empresas de Güemes sin datos catastrales cargan igual, con NULL en
    lote/matrícula/superficie — no se descartan del build.

Dry-run por defecto: sin --aplicar solo imprime conteos, no escribe nada.
"""
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # parques/
DATA = RAIZ / "data"
RAW = DATA / "raw"

PARQUE_SALTA_ID = 1
PARQUE_GUEMES_ID = 2
PARQUES = [
    {"id": PARQUE_SALTA_ID, "nombre": "Parque Industrial Salta"},
    {"id": PARQUE_GUEMES_ID, "nombre": "Parque Güemes"},
]

CAMPOS_EMPRESA = [
    "id", "nombre", "cuit", "rubro", "situacion", "contacto_nombre",
    "telefono_1", "telefono_2", "email_1", "email_2", "direccion",
    "pagina_web", "instagram", "facebook",
]
CAMPOS_LOTE = ["id", "parque_id", "numero", "superficie_m2"]
CAMPOS_MATRICULA = [
    "id", "lote_id", "numero_matricula", "empresa_id", "titularidad",
    "estado", "observacion",
]
CAMPOS_PARQUE = ["id", "nombre"]


def limpiar(valor: str) -> str:
    if not valor:
        return ""
    v = valor.strip()
    if v.lower() in ("no disponible", "sin cuit", "sin actividad", "n/a", ""):
        return ""
    return v.replace("\n", " ").strip()


def dos_valores(valor: str) -> tuple:
    """Separa un campo que puede traer 1 o 2 valores (dos emails, dos
    teléfonos) separados por salto de línea, "/" o ",". Nunca se descarta
    el segundo valor si está — el esquema de empresas_parque tiene
    telefono_1/telefono_2 y email_1/email_2 justo para esto."""
    if not valor:
        return "", ""
    partes = [limpiar(p) for p in re.split(r"[\n/,]", valor) if limpiar(p)]
    v1 = partes[0] if len(partes) > 0 else ""
    v2 = partes[1] if len(partes) > 1 else ""
    return v1, v2


def normalizar_cuit(valor: str) -> str:
    """Solo dígitos. CUIT válido tiene 11 — si no da 11, no se puede usar
    para cruzar contra cámaras (cross_link.py), pero se guarda igual tal
    cual venga por si sirve de referencia."""
    if not valor:
        return ""
    return re.sub(r"\D", "", valor)


def normalizar_estado(valor: str) -> str:
    v = (valor or "").strip().lower()
    if v in ("si", "sí", "escriturada", "escriturado"):
        return "escriturada"
    if v in ("no", "no escriturada", "no escriturado"):
        return "no escriturada"
    return ""  # desconocido — no se fabrica


# ----------------------------------------------------------------------
# Parque Güemes — "Contactos PI Güemes 2024" (52 empresas, sin catastro)
# ----------------------------------------------------------------------

def nombre_completo_guemes(empresa: str, razon_social: str) -> str:
    """Mismo criterio que match_pig_guemes.py: el Sheet separa "Empresa" y
    "Razón Social" ("FMF Argentina" + "S.R.L."), el resto del repo trae
    nombres concatenados ("FMF ARGENTINA S.R.L."). Evita duplicar la forma
    legal si "Empresa" ya termina en ella."""
    if razon_social and razon_social != "Otra":
        solo = re.sub(r"[^a-z0-9]", "", empresa.lower())
        rs = re.sub(r"[^a-z0-9]", "", razon_social.lower())
        if not solo.endswith(rs):
            return f"{empresa} {razon_social}"
    return empresa


def cargar_guemes(path: Path):
    empresas = []
    if not path.exists():
        print(f"[Güemes] no encuentro {path} — 0 empresas cargadas.")
        return empresas

    with path.open(encoding="utf-8", newline="") as f:
        filas = list(csv.reader(f))
    encabezado_idx = next(
        i for i, fila in enumerate(filas) if fila and fila[0].strip() == "ID"
    )
    claves = [c.strip() for c in filas[encabezado_idx]]

    for fila in filas[encabezado_idx + 1:]:
        if not fila or not fila[0].strip():
            continue
        reg = dict(zip(claves, fila))
        empresa = limpiar(reg.get("Empresa", ""))
        if not empresa:
            continue
        razon_social = limpiar(reg.get("Razón Social", ""))
        nombre = nombre_completo_guemes(empresa, razon_social)

        tel1, tel2 = dos_valores(reg.get("Teléfono", ""))
        mail1, mail2 = dos_valores(reg.get("email", ""))

        # El Sheet trae LinkedIn y una columna final sin nombre (notas de
        # verificación tipo "Confirmado" / "Sigue estando?") que no tienen
        # lugar en el esquema de empresas_parque (no hay campo linkedin ni
        # "nota"). Para no perder el dato, se guardan en la observación de
        # la matrícula placeholder en vez de descartarlos.
        linkedin = limpiar(reg.get("LinkedIn", ""))
        nota = limpiar(reg.get("", ""))
        obs_partes = []
        if nota:
            obs_partes.append(f"Nota del Sheet: {nota}")
        if linkedin:
            obs_partes.append(f"LinkedIn: {linkedin}")
        obs_partes.append(
            "Sin datos catastrales cargados (Contactos PI Güemes 2024 no "
            "trae lote/matrícula/superficie)."
        )

        empresas.append({
            "nombre": nombre,
            "cuit": normalizar_cuit(reg.get("Cuit", "")),
            "rubro": limpiar(reg.get("Rubro", "")),
            "situacion": "",
            "contacto_nombre": limpiar(reg.get("Contacto", "")),
            "telefono_1": tel1,
            "telefono_2": tel2,
            "email_1": mail1,
            "email_2": mail2,
            "direccion": limpiar(reg.get("Ubicación", "")) or "Parque Industrial Güemes, Salta",
            "pagina_web": limpiar(reg.get("Pag web", "")),
            "instagram": limpiar(reg.get("Instagram", "")),
            "facebook": "",
            # internos, se resuelven al renumerar ids
            "_lote": {"parque_id": PARQUE_GUEMES_ID, "numero": None, "superficie_m2": None},
            "_matricula": {
                "numero_matricula": None, "titularidad": None,
                "estado": "", "observacion": " | ".join(obs_partes),
            },
        })

    return empresas


# ----------------------------------------------------------------------
# Parque Industrial Salta — PI_Salta_Normalizado.xlsx, hoja Resumen_Empresas
# ----------------------------------------------------------------------

def separar_lista(valor: str) -> list:
    if not valor:
        return []
    return [p.strip() for p in re.split(r"[/,;]", valor) if p.strip()]


def cargar_salta(path: Path):
    empresas = []
    if not path.exists():
        print(f"[Salta] no encuentro {path} — esperando el archivo normalizado. 0 empresas cargadas.")
        return empresas

    columnas_esperadas = {
        "Empresa", "CUIT", "Lotes", "Matriculas", "Superficie_Total",
        "Titularidad", "Ocupante_Actual", "Rubro", "Situacion", "Contacto",
        "Direccion", "Telefono_1", "Telefono_2", "Email_1", "Email_2",
        "Presencia_Digital", "Estado_Matrícula", "Observación",
    }
    with path.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        faltantes = columnas_esperadas - set(lector.fieldnames or [])
        if faltantes:
            raise SystemExit(
                f"[Salta] {path} no tiene las columnas esperadas: {sorted(faltantes)}. "
                f"Columnas encontradas: {lector.fieldnames}. "
                "No se adivina el mapeo — corregir el CSV o el parser antes de seguir."
            )
        filas = list(lector)

    sin_desglosar_superficie = 0
    for reg in filas:
        empresa = limpiar(reg.get("Empresa", ""))
        if not empresa:
            continue
        tel1, tel2 = limpiar(reg.get("Telefono_1", "")), limpiar(reg.get("Telefono_2", ""))
        mail1, mail2 = limpiar(reg.get("Email_1", "")), limpiar(reg.get("Email_2", ""))

        # "web | instagram | facebook", siempre 3 partes (o "No disponible"
        # en cada una) — confirmado contra las 130 filas reales.
        web, insta, face = "", "", ""
        partes_digital = (reg.get("Presencia_Digital") or "").split("|")
        if len(partes_digital) >= 3:
            web, insta, face = (limpiar(p) for p in partes_digital[:3])

        numeros_lote = separar_lista(reg.get("Lotes", "")) or [None]
        numeros_matricula = separar_lista(reg.get("Matriculas", ""))
        titularidad = limpiar(reg.get("Titularidad", ""))
        estado = normalizar_estado(reg.get("Estado_Matrícula", ""))
        superficie_total = limpiar(reg.get("Superficie_Total", ""))

        observacion_base = limpiar(reg.get("Observación", ""))
        ocupante = limpiar(reg.get("Ocupante_Actual", ""))
        if ocupante and ocupante.lower() != empresa.lower():
            observacion_base = (
                f"{observacion_base} | Ocupante actual: {ocupante}"
                if observacion_base else f"Ocupante actual: {ocupante}"
            )

        # La superficie de la fuente es un total por empresa, no por lote.
        # Si hay 1 solo lote no hay ambigüedad. Con más de 1 no se reparte
        # a ciegas — se deja sin desglosar y se cuenta para el aviso del
        # dry-run.
        superficie_por_lote = superficie_total if len(numeros_lote) == 1 else ""
        if len(numeros_lote) > 1 and superficie_total:
            sin_desglosar_superficie += 1

        lotes_empresa = []
        for i, num_lote in enumerate(numeros_lote):
            num_matricula = numeros_matricula[i] if i < len(numeros_matricula) else None
            lotes_empresa.append({
                "_lote": {"parque_id": PARQUE_SALTA_ID, "numero": num_lote, "superficie_m2": superficie_por_lote},
                "_matricula": {
                    "numero_matricula": num_matricula, "titularidad": titularidad,
                    "estado": estado, "observacion": observacion_base,
                },
            })
        # matrículas de más (más matrículas que lotes listados) — cuelgan
        # del último lote en vez de perderse.
        for num_matricula in numeros_matricula[len(numeros_lote):]:
            lotes_empresa.append({
                "_lote": {"parque_id": PARQUE_SALTA_ID, "numero": numeros_lote[-1], "superficie_m2": ""},
                "_matricula": {
                    "numero_matricula": num_matricula, "titularidad": titularidad,
                    "estado": estado, "observacion": observacion_base,
                },
            })

        base = {
            "nombre": empresa,
            "cuit": normalizar_cuit(reg.get("CUIT", "")),
            "rubro": limpiar(reg.get("Rubro", "")),
            "situacion": limpiar(reg.get("Situacion", "")),
            "contacto_nombre": limpiar(reg.get("Contacto", "")),
            "telefono_1": tel1, "telefono_2": tel2,
            "email_1": mail1, "email_2": mail2,
            "direccion": limpiar(reg.get("Direccion", "")),
            "pagina_web": web, "instagram": insta, "facebook": face,
        }
        # una fila de empresas por cada lote/matrícula (comparten los
        # mismos datos de contacto — se resuelve al renumerar ids)
        for lm in lotes_empresa:
            fila = dict(base)
            fila["_lote"] = lm["_lote"]
            fila["_matricula"] = lm["_matricula"]
            empresas.append(fila)

    if sin_desglosar_superficie:
        print(
            f"[Salta] aviso: {sin_desglosar_superficie} empresas con más de "
            "1 lote y una sola Superficie_Total — no se reparte a ciegas, "
            "superficie_m2 queda vacío en esos lotes."
        )

    return empresas


# ----------------------------------------------------------------------
# Consolidar: cada "fila cruda" (empresa + 1 lote + 1 matrícula) se separa
# en las 3 tablas normalizadas, agrupando por nombre de empresa para no
# duplicar la ficha de contacto por cada lote.
# ----------------------------------------------------------------------

def consolidar(filas_crudas: list):
    empresas, lotes, matriculas = [], [], []
    empresa_id_por_nombre = {}
    # El número de lote es un identificador catastral único dentro del
    # parque (confirmado contra los tabs crudos de "Contactos PI Salta" y
    # "Sistema güemes": un mismo ID_LOTES se repite en varias filas cuando
    # el lote tiene más de una matrícula, ej. CERAMICA ALBERDI con 3
    # matrículas bajo 1 solo lote). Se dedupe por (parque_id, numero) para
    # no crear un lote nuevo por cada matrícula que en realidad comparte
    # terreno. Cuando el número es desconocido (Güemes sin catastro) no
    # hay nada que deduplicar — cada empresa se queda con su propio lote
    # placeholder.
    lote_id_por_clave = {}
    siguiente_empresa_id = 1
    siguiente_lote_id = 1
    siguiente_matricula_id = 1

    for fila in filas_crudas:
        clave = fila["nombre"].strip().lower()
        if clave not in empresa_id_por_nombre:
            eid = siguiente_empresa_id
            siguiente_empresa_id += 1
            empresa_id_por_nombre[clave] = eid
            empresas.append({
                "id": eid, "nombre": fila["nombre"], "cuit": fila["cuit"],
                "rubro": fila["rubro"], "situacion": fila["situacion"],
                "contacto_nombre": fila["contacto_nombre"],
                "telefono_1": fila["telefono_1"], "telefono_2": fila["telefono_2"],
                "email_1": fila["email_1"], "email_2": fila["email_2"],
                "direccion": fila["direccion"], "pagina_web": fila["pagina_web"],
                "instagram": fila["instagram"], "facebook": fila["facebook"],
            })
        eid = empresa_id_por_nombre[clave]

        parque_id = fila["_lote"]["parque_id"]
        numero = fila["_lote"]["numero"] or ""
        clave_lote = (parque_id, numero) if numero else None
        if clave_lote is not None and clave_lote in lote_id_por_clave:
            lid = lote_id_por_clave[clave_lote]
        else:
            lid = siguiente_lote_id
            siguiente_lote_id += 1
            if clave_lote is not None:
                lote_id_por_clave[clave_lote] = lid
            lotes.append({
                "id": lid, "parque_id": parque_id, "numero": numero,
                "superficie_m2": fila["_lote"]["superficie_m2"] or "",
            })

        mid = siguiente_matricula_id
        siguiente_matricula_id += 1
        matriculas.append({
            "id": mid, "lote_id": lid,
            "numero_matricula": fila["_matricula"]["numero_matricula"] or "",
            "empresa_id": eid,
            "titularidad": fila["_matricula"]["titularidad"] or "",
            "estado": fila["_matricula"]["estado"] or "",
            "observacion": fila["_matricula"]["observacion"] or "",
        })

    return empresas, lotes, matriculas


def escribir_csv(path: Path, filas: list, campos: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def main():
    aplicar = "--aplicar" in sys.argv

    crudas = []
    crudas += cargar_guemes(RAW / "pi_guemes.csv")
    crudas += cargar_salta(RAW / "pi_salta.csv")

    empresas, lotes, matriculas = consolidar(crudas)

    print("\n--- Dry-run: conteos por parque ---")
    for parque in PARQUES:
        lotes_p = [l for l in lotes if l["parque_id"] == parque["id"]]
        lote_ids_p = {l["id"] for l in lotes_p}
        matriculas_p = [m for m in matriculas if m["lote_id"] in lote_ids_p]
        empresa_ids_p = {m["empresa_id"] for m in matriculas_p}
        sin_catastro = sum(
            1 for m in matriculas_p
            if not m["numero_matricula"] and not m["titularidad"]
        )
        print(
            f"  {parque['nombre']}: {len(empresa_ids_p)} empresas, "
            f"{len(lotes_p)} lotes, {len(matriculas_p)} matrículas "
            f"({sin_catastro} matrículas sin datos catastrales)"
        )
    print(f"  TOTAL: {len(empresas)} empresas, {len(lotes)} lotes, {len(matriculas)} matrículas\n")

    if not aplicar:
        print("Dry-run only — no se escribió nada. Correr con --aplicar para generar los CSV normalizados.")
        return

    escribir_csv(DATA / "parques.csv", PARQUES, CAMPOS_PARQUE)
    escribir_csv(DATA / "empresas_parque.csv", empresas, CAMPOS_EMPRESA)
    escribir_csv(DATA / "lotes.csv", lotes, CAMPOS_LOTE)
    escribir_csv(DATA / "matriculas.csv", matriculas, CAMPOS_MATRICULA)
    print(f"Escrito en {DATA}/: parques.csv, empresas_parque.csv, lotes.csv, matriculas.csv")


if __name__ == "__main__":
    main()
