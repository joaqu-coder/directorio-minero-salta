# Parques Industriales — Güemes y Salta

Sitio estático independiente del directorio de cámaras (CMS/CAPEMISA/UIS)
que vive en la raíz del repo. Mismo repo, mismo lenguaje visual, pipeline y
esquema de datos propios — el modelo catastral de un parque (lotes,
matrículas, superficie, titularidad) no es el de una membresía por rubro.

## Por qué un sitio aparte

Una empresa de cámaras tiene rubros y membresías. Una empresa de un parque
tiene lotes, y cada lote puede tener varias matrículas con distinta
titularidad (escriturada a nombre de la empresa, o todavía a nombre del
Ente o de una persona física). Forzar eso al esquema de cámaras hubiera
significado inventar una "cámara" llamada Parque X con "rubros" falsos —
exactamente lo que **no** se quiere seguir haciendo (ver más abajo).

Si una empresa existe en los dos sitios (mismo CUIT en cámaras y en un
parque) **no se fusiona el registro**: cada sitio muestra su propia ficha,
con un link "también en [otro sitio] →". El cruce es solo por CUIT al
momento del build (`cross_link.py`), nunca una fusión de esquema.

## Pipeline

```
data/raw/pi_salta.csv  ─┐
data/raw/pi_guemes.csv ─┴─> load_data.py ─> data/{parques,lotes,matriculas,empresas_parque}.csv
                                                          │
                                                          v
                                              build_parques_db.py
                                                          │
                                              ┌───────────┴───────────┐
                                              v                       v
                                       parques.db (gitignored)   data/parques.json
                                                                       │
                                                                       v
                                                              scripts/cross_link.py
                                                        (lee también ../data/empresas.json)
                                                                       │
                                                                       v
                                                              data/cruce.json
```

- `data/raw/*.csv` son los exports tal cual bajan de la fuente (Excel o
  Google Sheet) — el input manual de `load_data.py`. Se commitean junto
  con los normalizados: no hay scraping que los regenere solo, así que son
  la única copia de qué vino de dónde.
- `data/{parques,lotes,matriculas,empresas_parque}.csv` son el output de
  `load_data.py` — **source of truth en git**, mismo criterio que
  `/data/empresas.csv` en la raíz del repo.
- `parques.db` y `data/parques.json` son build artifacts de
  `build_parques_db.py`. `parques.db` está gitignoreado; `parques.json` sí
  se commitea porque el frontend lo consume directo (no hay backend).
- `data/cruce.json` es el único archivo que toca `cross_link.py`, y lo
  genera leyendo `../data/empresas.json` (cámaras) + `data/parques.json`
  (este sitio) — **nunca escribe en ninguno de los dos**.

## Esquema

| Tabla | Campos | Notas |
|---|---|---|
| `parques` | id, nombre | "Parque Güemes", "Parque Industrial Salta" |
| `lotes` | id, parque_id, numero, superficie_m2 | 1 lote puede tener N matrículas |
| `matriculas` | id, lote_id, numero_matricula, empresa_id, titularidad, estado, observacion | `estado`: `escriturada` \| `no escriturada`. `titularidad` es texto libre — puede ser la empresa o una persona física si todavía no escrituró |
| `empresas_parque` | id, nombre, cuit, rubro, situacion, contacto_nombre, telefono_1, telefono_2, email_1, email_2, direccion, pagina_web, instagram, facebook | 1 empresa puede tener N lotes vía `matriculas.empresa_id` |

**Reglas de negocio (no reabrir):**
- Todas las empresas de un parque son propietarias (escrituradas o no). No
  existe "inquilino puro alquilando al ente" — no hay tabla `ocupaciones`.
- `estado="no escriturada"` solo dice que la matrícula sigue a nombre del
  Ente o de una persona física — no implica trámite, pendiente o rechazo.
  Si el Excel/Sheet no dice el motivo, no se inventa.
- Los casos con `Situacion="Alquilada"` (empresa propietaria que alquila a
  OTRA empresa del parque) quedan fuera de scope: no se modela quién es el
  inquilino todavía.

## Dry-run

`load_data.py` **no escribe nada sin `--aplicar`**. Sin el flag, imprime
conteos (lotes / matrículas / empresas por parque) para revisar antes de
generar los CSV normalizados. Correr siempre el dry-run primero:

```bash
cd parques/scripts
python load_data.py            # dry-run: solo conteos
python load_data.py --aplicar  # escribe los CSV normalizados en data/
```

## Para editar o agregar una empresa

1. Editar la fuente correspondiente:
   - **Parque Salta**: el Excel/Sheet de origen (ver `data/raw/pi_salta.csv`
     para el formato esperado) → exportar a CSV → reemplazar
     `parques/data/raw/pi_salta.csv`.
   - **Parque Güemes**: el Google Sheet "Contactos PI Güemes 2024" → Archivo
     → Descargar → CSV → reemplazar `parques/data/raw/pi_guemes.csv`.
2. Correr el pipeline completo desde `parques/scripts/`:
   ```bash
   python load_data.py --aplicar
   python build_parques_db.py
   python cross_link.py
   ```
3. Revisar el resumen que imprime `build_parques_db.py` (empresas por
   parque, cuántas "no escrituradas", y cuántas con cruce a cámaras — esto
   último solo sale si `data/cruce.json` ya existe de una corrida previa;
   la primerísima vez va a decir "cruce.json no existe todavía", normal —
   correr `build_parques_db.py` una segunda vez después de `cross_link.py`
   si se quiere ver ese número).
4. `git add parques/` y commit + push.

No hay API, no hay base de datos viva, no hay edición desde el frontend.
Cualquier cambio de datos pasa siempre por este flujo de 4 pasos.
