# Auditoría — Directorio Minero Salta

**Fecha:** 2026-10-30 · **Rama:** `claude/gallant-keller-kl9o2k` · **No mergeado a `main`.**

## Resumen

1. **El sitio en vivo no se actualiza desde el 2026-08-28.** Las 9 corridas semanales desde el 2026-08-31 terminaron en rojo, y los commits de datos que sí llegaron al repo nunca se deployaron. Causa en dos partes: (a) el paso final de deploy a Cloudflare falla con `Invalid account ID` (el secret `CLOUDFLARE_ACCOUNT_ID` está mal configurado) y (b) el push del bot usa `GITHUB_TOKEN`, que no dispara `pages.yml`. **Parcheado en la rama; falta merge a `main` y tu confirmación.**
2. **El historial de cambios tiene 41 altas y 41 bajas fantasma** (2026-08-27 y 2026-08-31). Vienen de integrar y revertir la hoja del Parque Industrial Güemes. No es un error de scraping. `cambios.csv` es append-only, así que se documenta, no se reescribe.
3. **Hay un duplicado probable sin fusionar** (CENTRO DISTRIBUIDOR / LOGISTICA DEL ALTO) y **datos personales en un repo público**. Son decisiones tuyas.
4. **Este entorno no puede acceder a las tres fuentes** (`cmsalta.com.ar`, `capemisa.com.ar`, `uis.com.ar` devuelven 403 del proxy de salida). No hay fixtures HTML, no hay conteo contra la API REST y no hay muestra de logos remotos. Esto queda como pendiente.

## Bloqueado por red (no hecho)

- Captura de fixtures HTML de las tres fuentes (Fase 1).
- Conteo independiente `X-WP-Total` / paginación UIS contra cada scraper (Fase 0).
- Verificación de placeholder de CAPEMISA por hash perceptual (necesita los bytes del placeholder).
- Muestra de 50 logos remotos para medir calidad real. Los 384 logos están en el CSV como URLs remotas, así que solo se pueden revisar con acceso a esos hosts.
- Ejecución real del scraper (`scrape_*.py`). Requiere red y `data/staging/`, que está gitignoreado.

## Métricas (línea base, desde los CSV commiteados)

| Métrica | Valor |
|---|---|
| Empresas / ids únicos / `nombre_norm` únicos | 384 / 384 / 384 |
| Membresías (CAPEMISA / UIS / CMS) | 445 (349 / 67 / 29) |
| Empresas con más de una cámara | 12 |
| Teléfono / email / web | 90% / 88% / 71% |
| Instagram / Facebook / LinkedIn | 31% / 24% / 22% |
| Contacto (representante) / descripción / ubicación | 75% / 18% / 24% |
| CUIT | 0% (columna vacía en todo el dataset) |
| Logo: `camara` / `sitio_oficial` / `placeholder` | 320 / 53 / 11 (97% no-placeholder **por etiqueta del pipeline**, no verificado visualmente) |
| Candidatos sin resolver | 6 |
| Logos huérfanos en `data/logos/` | 26 |
| Export JSON = CSV (ids) | Sí (384 = 384) |

**Criterios de CLAUDE.md:** ver la sección de cambios (desmarqué 2 criterios). El de logos (≥ 90%) sigue sin marcar. El de < 2 s en 4G y el de Web Share en Android siguen sin verificarse.

## Hallazgos

### 1. Crítico — el sitio en vivo congelado y el semanal en rojo
- Último deploy exitoso de GitHub Pages: 2026-08-28 (`pages.yml`).
- `Scrape semanal`: 9 de 9 fallidos desde el 2026-08-31 (17–28 min cada uno).
- Log del fallo (run `40352660670`): el commit y el push sí ocurren; falla el paso "Deploy Cloudflare Pages" con `Invalid account ID set in CLOUDFLARE_ACCOUNT_ID`.
- `deploy.yml` (Cloudflare, en push a `main`) también falla: los 3 runs más recientes que muestra `gh` (desde el 2026-08-27) están en rojo.
- Causa de fondo: el push con `GITHUB_TOKEN` no dispara `pages.yml`, así que el deploy de Pages nunca corre tras un commit del bot.

**Cambio aplicado:** `pages.yml` ahora escucha `workflow_run` de `Scrape semanal` y `Enriquecer logos (manual)`, y solo deploya si el run terminó en `success`. Se quitó el paso de Cloudflare de `scrape-semanal.yml`.

### 2. Alto — 41 altas/bajas fantasma en el historial
- 41 altas el 2026-08-27 (IDs 392–432) y las mismas 41 bajas el 2026-08-31. Ninguno de esos IDs sigue en `empresas.csv`.
- Origen: commits `41e499b` (integrar hoja Güemes) y `2a0452e` (revertir, "-41 bajas").
- Las 11 modificaciones de `cuit` del 2026-08-27 son parte del mismo run. La columna `cuit` está vacía en todo el dataset: se escribe en el changelog pero no hay fuente que la llene.
- Las otras 19 bajas sí son reales (no están en el CSV actual).
- **No reescrito.** Decisión pendiente: anotar en `cambios.csv` o aceptarlo como historial.

### 3. Alto — invalidación de caché del service worker rota
- `pages.yml` hacía `sed` sobre `const CACHE = 'dir-v1'`, pero `sw.js` declara `dir-v2`. El `sed` nunca aplicaba.
- **Cambio aplicado:** regex `dir-[^']+` y un `grep` que falla el job si el reemplazo no ocurre.

### 4. Medio — URLs sin validación de esquema en la ficha
- `index.html` ponía `esc(e.web|instagram|facebook|linkedin)` en `href`. `esc` escapa comillas, no esquemas: un `javascript:` de un dato scrapeado ejecutaría al hacer clic.
- Verificado con Playwright: la versión original genera 2 links `javascript:` con el payload de prueba; la parcheada genera 0.
- **Cambio aplicado:** helper `safeUrl` (solo `http(s)`) en esos cuatro `href`.
- También: el nombre de cámara en los chips se escapa (`esc`).

### 5. Medio — el banner de novedades se imprimía
- En el PDF A4 salía "2 empresas nuevas esta semana. Ver detalles" y el botón de cerrar.
- **Cambio aplicado:** clase `no-print` en `#bannerNovedades`. Verificado rasterizando la primera página del PDF.

### 6. Medio — 26 logos huérfanos en `data/logos/`
- Ningún `logo` del JSON apunta a `data/logos/`: todos son URLs remotas.
- 16 archivos no tienen empresa actual con ese nombre; la mayoría coincide con nombres de las 41 bajas fantasma (no verifiqué uno por uno). 10 corresponden a empresas actuales que ya tienen logo remoto (p. ej. `FMFArgentina.png`, `ceramicaSalte#U00f1a.png`).
- `ceramicaSalte#U00f1a.png` tiene un `#` en el nombre: si alguna vez se referencia por URL, el `#` se interpreta como fragmento.
- **No borrado.** Decisión pendiente. Test xfail en `tests/test_datos.py`.

### 7. Medio — posible duplicado sin fusionar
- CENTRO DISTRIBUIDOR S.A. y LOGISTICA DEL ALTO S.R.L. comparten teléfono `(0387) 403 2318`, email `contacto@logisticadelalto.com` y representante `micaela ohse`.
- Están en `candidatos_revision.csv` (regla representante), que es el comportamiento correcto. **No fusionado.** Test xfail.
- Otros pares de nombres similares (≥ 88 con rapidfuzz): AB CONSTRUCCIONES / AGI CONSTRUCCIONES, AF INGENIERIA / DAM INGENIERIA, BÖHM ASESORES / SAS ASESORES. Los dos primeros ya están en candidatos. El tercero no está, y no verifiqué si es el mismo grupo: queda para revisión manual.

### 8. Medio — datos personales en un repo público
- `gh api` confirma `visibility: public`.
- El CSV incluye nombres de representantes (`contacto_nombre`, 289 filas) y teléfonos/emails.
- CLAUDE.md exige repo público para GitHub Pages. **Decisión pendiente** tuya (Ley 25.326): mantener, anonimizar o publicar solo el JSON del frontend.

### 9. Bajo — contradicciones en CLAUDE.md
- Describe `deploy.yml` como deploy de Pages; en realidad es Cloudflare.
- No menciona `pages.yml`, `enriquecer-logos-manual.yml`, `enriquecer_criticas.py`, `enriquecer_gaps.py`, `enriquecer_logos.py` ni `match_pig_guemes.py`.
- Hay criterios marcados sin evidencia (ver abajo). No reescribí la sección de estructura: pendiente.

### 10. Bajo — `deploy.yml` sigue activo
- Corre en cada push a `main` y falla. Decisión pendiente: borrarlo o desactivarlo.

## Cambios en esta rama

| Archivo | Cambio |
|---|---|
| `.github/workflows/pages.yml` | `workflow_run` sobre datos, guard de `success`, fix del `sed` de CACHE con verificación |
| `.github/workflows/scrape-semanal.yml` | Quitado el deploy de Cloudflare; `concurrency: datos` |
| `index.html` | `safeUrl` en 4 `href` de la ficha; `esc` en chips de cámara; `no-print` en banner |
| `scraper/requirements.txt` | Versiones fijadas (las que resuelve pip hoy) |
| `CLAUDE.md` | 2 criterios desmarcados con evidencia |
| `tests/test_datos.py` | Invariantes de datos (sin red), 2 xfail documentados |
| `tests/frontend_check.mjs` | Layout 360/390 px, escape + esquemas con payload hostil, PDF A4 |
| `docs/auditoria.md` | Este reporte |

## Verificación

- `python3 -m pytest tests/test_datos.py -q` → 9 passed, 2 xfailed.
- `node tests/frontend_check.mjs <HEAD>` (baseline) → falla en "ningún link javascript:" (2 encontrados).
- `node tests/frontend_check.mjs .` (parcheado) → todos los chequeos pasan (0 scroll horizontal en 360/390 px, 0 errores de JS, 0 payloads ejecutados, PDF A4 generado).
- Impresión: primera página rasterizada; el banner ya no aparece.
- `actionlint .github/workflows/*.yml` → sin errores.
- Pendiente de verificación en GitHub: que `pages.yml` dispare tras un `Scrape semanal` real. Solo se puede comprobar al mergear a `main` y esperar un run.

## No verificado

- Lighthouse (criterio < 2 s en 4G): no corrido.
- Web Share API en Android: requiere dispositivo real.
- Referencia de diseño "Antigravity v2": no está en el repo.

## Pendiente de Judas

1. **Merge a `main`** de esta rama para que el deploy se active. Por la regla de CLAUDE.md y tu instrucción, no lo hice.
2. **Secret `CLOUDFLARE_ACCOUNT_ID`**: revisarlo en GitHub, o confirmar que Cloudflare ya no se usa y borrar `deploy.yml`.
3. **Privacidad**: decidir si los datos personales de representantes y contactos pueden estar en un repo público.
4. **Duplicado** CENTRO DISTRIBUIDOR / LOGISTICA DEL ALTO: fusionar o confirmar que son empresas distintas.
5. **Logos huérfanos**: borrar los 26 archivos de `data/logos/` o conservarlos.
6. **Historial fantasma**: anotar en `cambios.csv` o dejarlo tal cual.
7. **`cuit`**: definir fuente o quitar el campo del changelog.
8. **Referencia Antigravity v2**: pasarme la referencia real.
9. **Cuándo correr el semanal** tras el merge, para validar en vivo (o correrlo manualmente con `workflow_dispatch`).
