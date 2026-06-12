# CLAUDE.md — Directorio Minero Salta

## Proyecto

App de consulta de empresas asociadas a cámaras empresariales de Salta (CMS Minería, CAPEMISA, UIS), con base SQLite, frontend único mobile-first, scraping semanal automatizado con detección de cambios, y matching de entidades entre cámaras.

Usuario: Judas. Comunicación en español, directa, sin relleno. Patches quirúrgicos, no rewrites.

---

## Principio de eficiencia (regla de operación)

**Máximo resultado, mínimo gasto de tokens.**

1. **Usar ECC antes de improvisar.** Este repo tiene instalado [everything-claude-code](https://github.com/affaan-m/everything-claude-code): 64 agents, 197 skills, 84 commands en `~/.claude/`. Antes de escribir código o lanzar búsquedas, verificar si existe un skill o agente que ya lo resuelve (`/ecc-guide` para navegar el catálogo).

2. **Un recorrido, no varios.** Si una tarea requiere múltiples pasadas (scraping, enrichment, búsqueda), detectar el patrón de loop temprano y reemplazarlo por un trigger delta — solo procesar lo que cambió, nunca re-procesar todo.

3. **Paralelizar independientes, serializar dependientes.** Lanzar agentes en paralelo para ángulos independientes. No lanzar un agente si el resultado no cambia la acción siguiente.

4. **Frenar ante rendimientos decrecientes.** Si después de 2 intentos una fuente sigue bloqueada (403, timeout, sin datos), abandonar esa vía y reportar el estado — no seguir quemando requests.

5. **Subagentes para contexto grande.** Usar `Agent` para exploración amplia del codebase o investigación multi-fuente. Mantener el contexto principal limpio para decisiones.

6. **Commits atómicos en cada cambio funcional.** No acumular cambios — commit + push después de cada unidad de trabajo para no perder trabajo en sesiones efímeras.

---

## Decisiones fijas (NO renegociar)

| Decisión | Valor |
|---|---|
| Base de datos | SQLite (`directorio.db`), build artifact. CSVs en `/data` como source of truth en Git |
| Scraper | **Scrapling** (verificado: BSD 3-Clause, gratuito, v0.4.9) |
| Frontend | **Single-file HTML** (`index.html`), sin frameworks, sin build step |
| Estilo | Dark theme, mobile-first, minimalista. Fuentes: Manrope (UI) + DM Mono (datos) |
| Hosting frontend | **GitHub Pages** — deploy automático vía GitHub Actions (`.github/workflows/pages.yml`). Repo público requerido. URL: `https://<owner>.github.io/<repo>/`. Ver regla general de hosting más abajo. |
| Scheduler | GitHub Actions, cron semanal (lunes 06:00 ART = `0 9 * * 1` UTC) |
| Datos en frontend | SQLite exportado a JSON estático (`empresas.json`) consumido por fetch — NO servidor backend |

**Instalación Scrapling** (requiere deps no declaradas — `playwright` es import-time aunque solo se use fetching estático):

```bash
pip install scrapling curl_cffi browserforge orjson playwright
```

**API Scrapling 0.4.9** (verificado): `Fetcher.get(url, stealthy_headers=True, follow_redirects=True)` → Response con `.status`, `.css(sel)`. `css('x::text').get()` → TextHandler con `.clean()`; `css('x::text').getall()` → lista; `css('a::attr(href)').get()`. NO existe `css_first`. `retries=0` rompe la sesión interna ("No active session available") — usar `retries>=1`. Helpers en `scraper/common.py`: `texto(nodo, sel)`, `attr(nodo, sel)`.

---

## Regla general de hosting (aplica a este y futuros proyectos)

**Punto de partida siempre: GitHub Pages.**
- Repo público + workflow `.github/workflows/pages.yml` con `actions/deploy-pages`.
- Cero cuentas externas, cero secrets, deploy automático en cada push a `main`.
- Suficiente para: sitios estáticos, SPAs, frontends con fetch a JSON, portfolios, directorios.

**Escalar a otra plataforma solo si GitHub Pages no alcanza:**

| Necesidad | Plataforma |
|---|---|
| CDN edge global + headers custom + redirects complejos | **Cloudflare Pages** |
| Serverless functions junto al frontend (API routes) | **Cloudflare Pages** (Workers) o **Vercel** |
| Preview deploys por PR + entornos múltiples | **Vercel** o **Netlify** |
| Backend full (DB, auth, workers de larga duración) | **Fly.io** o **Railway** |
| Dominio propio con SSL automático | Cualquiera de los anteriores (todos lo ofrecen gratis) |

**Criterio de decisión al arrancar un proyecto nuevo:**
1. ¿Es estático o SPA con datos en JSON/CDN? → **GitHub Pages**.
2. ¿Necesita lógica server-side o edge functions? → evaluar Cloudflare Pages primero (más barato), luego Vercel.
3. ¿Necesita base de datos persistente o procesos largos? → Fly.io o Railway.

El workflow mínimo de GitHub Pages:
```yaml
# .github/workflows/pages.yml
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - name: Armar dist
        run: mkdir -p dist && cp index.html dist/  # ajustar según proyecto
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist/
      - uses: actions/deploy-pages@v4
        id: deployment
```

---

## Fuentes verificadas (junio 2026)

### 1. cmsalta.com.ar — Cámara de la Minería ✅ VERIFICADO
- WordPress, HTML server-side, sin JS dinámico, sin Cloudflare challenge.
- Lista: `https://cmsalta.com.ar/socios/` → `ul.sucursales-list li`: logo (`span.logo img`, thumbnail `-150x150` — quitar sufijo para tamaño completo), nombre (`span.info h5`), ubicación (`span.info p`), link a `/asociados/{slug}/`.
- Detalle: `div.datos` con pares `h6` (label) / `p` (valor): Actividades, Mineral, Fase del Proyecto, Producto final, Dirección. Link web: `a[href^=http]` externo en `div.datos-container`.
- 30 socios. Logos hosteados por la cámara: hit rate ~95%.
- Teléfono/email: escasos en fichas (~20%). Enriquecer desde sitio oficial.

### 2. capemisa.com.ar — CAPEMISA ✅ VERIFICADO
- WordPress + Elementor + Astra, HTML server-side.
- 16 categorías con URL propia (ver dict `CATEGORIAS` en `scrape_capemisa.py`). **Paginación server-side**: `/{categoria}/page/N/`, 20 cards por página.
- Card = `article.elementor-post.type-socio`: logo (primer `img`), nombre (`h3.elementor-heading-title`), `li.elementor-icon-list-item` con prefijos `Actividad:` / `Dirección:` / `Teléfono:` / `Email:` / `Contacto:`; "Página web" es un `a` externo. Link "Más Info" a `/socio/{slug}/`.
- **Las cards traen TODOS los campos → no hace falta visitar fichas individuales.**
- REST API útil para verificación: `/wp-json/wp/v2/socio` (CPT expuesto), `/wp-json/wp/v2/categoria` (16 términos con counts).
- ~346 membresías, ~296 empresas únicas (junio 2026). Una misma empresa aparece en varias categorías → crítico para matching.
- Logos placeholder: si `src` contiene `LogoCapemisa` (case-insensitive), es el logo de la cámara → `logo_placeholder=1`, enriquecer desde sitio oficial.

### 3. uis.com.ar — Unión Industrial Salta ✅ VERIFICADO (Fase 0 junio 2026)
- Directorio público, sin login. WordPress server-side (meta generator dice Drupal: ignorar, es falso).
- Lista: `https://uis.com.ar/asociados/?sf_paged=N` (paginación Search&Filter, 24 por página, ~69 socios) → `li.card_item` con logo (`img`) y link a `/socios/{slug}/`.
- Detalle `/socios/{slug}/` RICO: `section#page-header` → logo (`.logo img`), nombre (`.content h2`), `.datos span.empresa` = [rubro, ubicación]. `#entry-content .hentry p` = descripción. `div.datos-asociado > div` con íconos FontAwesome: `fa-location-dot`→dirección, `fa-phone`→teléfono, `fa-envelope`→email, `fa-globe`→sitio web (href del `a`).
- Rubro también en breadcrumb JSON-LD (`rubro_categories`).

### Enriquecimiento (segunda pasada — `enriquecer.py`)
Para cada dominio único con sitio web: fetch del home y extraer:
1. `<img>` con "logo" en src (preferir SVG) > `link rel=icon` SVG > `og:image` > icon raster → logo de alta calidad
2. `mailto:`, `tel:`, links a perfiles de `instagram.com/`, `facebook.com/`, `linkedin.com/`
3. `twitter:site` / `twitter:creator` de meta tags
Caso real verificado: betonsrl.com.ar expone logo SVG en `/public/images/logo-beton-srl.svg` + `@betonsrl` en metas.
Salida: `data/staging/enriquecimiento.json` keyed por dominio. `matching.py` lo aplica solo a campos vacíos (el logo de sitio oficial reemplaza placeholders).

---

## Pipeline de datos

```
scrape_cms.py ─┐
scrape_capemisa.py ├─> data/staging/*.json ─> enriquecer.py ─> matching.py ─> data/*.csv ─> build_db.py ─> directorio.db + data/empresas.json
scrape_uis.py ─┘
```

- `data/staging/` y `directorio.db` están gitignoreados; los CSVs son el source of truth.
- `matching.py` mantiene ids estables (diff por `nombre_norm` contra `empresas.csv`).
- Primera corrida (CSV vacío): NO genera cambios tipo "alta" (la carga inicial no es novedad).
- Matches difusos (Levenshtein ≥ 0.85) NO se fusionan: van a `data/candidatos_revision.csv`.

## Esquema SQLite

Ver `ESQUEMA` en `scraper/build_db.py` (tablas `empresas` — incluye `descripcion`, `ubicacion`, `cuit` nullable —, `membresias`, `cambios`, `representantes`). `idx_empresas_norm` UNIQUE sobre `nombre_norm`.

## Matching de entidades (requisito clave)

Una empresa que aparece en CMS y CAPEMISA, o en dos rubros de CAPEMISA, debe ser **UN solo registro** con N membresías.

Cascada de matching (en `matching.py`):
1. `nombre_norm` exacto → match.
2. Sitio web (dominio normalizado, sin www) coincidente → match.
3. `nombre_norm` con similitud Levenshtein ≥ 0.85 → candidato, loggear para revisión.
4. Representante (`contacto_nombre` normalizado) coincidente + rubros relacionados → candidato.

Prioridad de fuente al fusionar campos en conflicto: CAPEMISA > UIS > CMS.

La UI muestra en la ficha: badges de todas las cámaras/rubros, y si el representante figura en otra empresa, link cruzado.

## Detección de cambios y notificaciones

Cada run semanal: scrape → diff contra CSVs por `nombre_norm` (altas / bajas / modificaciones campo a campo / nuevo_rubro) → append a `data/cambios.csv` → badge "🔔 N novedades" en frontend (visto con localStorage) → commit message resume (`feat(data): +2 altas, 3 modificaciones — run YYYY-MM-DD`).

## Frontend — specs

Single-file `index.html`. Sin dependencias externas salvo Google Fonts (Manrope, DM Mono).

- **Lista**: cards compactas → logo 200px (redondeado, lazy-load, fallback iniciales), nombre, rubro badge, cámara badge.
- **Ficha** (modal): logo grande, actividad, dirección, teléfono (`tel:`), email (`mailto:`), redes, sitio web, representante, membresías, historial de cambios.
- **Buscador**: input único (nombre, actividad, rubro, representante) + chips por cámara y rubro.
- **Compartir**: Web Share API; ficha individual via `?empresa=slug`; fallback clipboard en desktop.
- **Imprimir**: `@media print` → lista filtrada limpia en A4, una empresa por bloque.
- Dark theme default. Diseño consistente con Antigravity v2.

## Estructura del repo

```
/
├── CLAUDE.md
├── index.html                  # frontend completo
├── data/
│   ├── empresas.csv            # source of truth
│   ├── membresias.csv
│   ├── cambios.csv             # changelog acumulado
│   ├── candidatos_revision.csv # matches difusos para revisión manual
│   └── empresas.json           # export para frontend (generado)
├── scraper/
│   ├── common.py               # fetch + normalización + helpers selectores
│   ├── scrape_cms.py
│   ├── scrape_capemisa.py
│   ├── scrape_uis.py
│   ├── enriquecer.py
│   ├── matching.py
│   ├── build_db.py
│   └── requirements.txt
└── .github/workflows/
    ├── scrape-semanal.yml      # cron lunes 06:00 ART (+ deploy al final)
    └── deploy.yml              # deploy Pages en cada push a main
```

Repo: `https://github.com/joaqu-coder/directorio-minero-salta` (privado).
Deploy: ambos workflows omiten el deploy con un notice si falta `CLOUDFLARE_API_TOKEN`.
Para activarlo (una sola vez, token en dash.cloudflare.com → My Profile → API Tokens → template "Edit Cloudflare Workers" o permiso `Cloudflare Pages:Edit`):

```bash
gh secret set CLOUDFLARE_API_TOKEN --repo joaqu-coder/directorio-minero-salta
gh secret set CLOUDFLARE_ACCOUNT_ID --repo joaqu-coder/directorio-minero-salta
gh workflow run deploy.yml --repo joaqu-coder/directorio-minero-salta
```

## Comandos permitidos

Lectura: `gh pr list`, `gh pr view`, `gh run list`, `gh issue list`, `git log`, `git fetch`
Escritura: `git add`, `git commit`, `git push`, `gh pr create`, `gh pr comment`, `gh issue create`
**Requieren confirmación explícita del usuario**: `gh pr merge`, `gh pr close`, `git push --force`

## Criterios de aceptación

- [x] Scrape completo corre en < 10 min sin bloqueos (delay 2-3s entre requests al mismo host)
- [x] Cero duplicados: misma empresa en 2 cámaras = 1 registro
- [ ] ≥ 90% empresas con logo no-placeholder tras enriquecimiento
- [ ] Frontend carga en < 2s en 4G, usable a 360px de ancho
- [ ] Compartir ficha individual funciona en Android (Web Share API)
- [ ] Impresión de lista filtrada sale legible en A4
- [ ] Run semanal commitea solo si hay cambios, con resumen en el mensaje
