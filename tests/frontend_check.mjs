// Chequeo de frontend con Playwright (Chromium ya instalado en el entorno).
// Uso: node tests/frontend_check.mjs [carpeta_a_servir] [carpeta_pdf]
// Sirve la carpeta (por defecto la raíz del repo), prueba 360/390 px sin
// scroll horizontal, abre una ficha, inyecta una empresa hostil en el JSON
// y verifica que no ejecute código ni genere links javascript:, y exporta
// la lista a PDF A4. Sale con código 1 ante cualquier fallo.
import { spawn } from 'node:child_process';
import { readFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// require (CJS) respeta NODE_PATH; el import ESM no. Playwright viene instalado global.
const { chromium } = createRequire(import.meta.url)('playwright');

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SERVIR = resolve(process.argv[2] || RAIZ);
const CARPETA_PDF = resolve(process.argv[3] || join(RAIZ, 'tests', 'out'));
const PORT = 8799;
const BASE = `http://127.0.0.1:${PORT}/`;
mkdirSync(CARPETA_PDF, { recursive: true });

const fallos = [];
const check = (cond, msg) => { if (!cond) fallos.push(msg); console.log(`${cond ? 'OK  ' : 'FAIL'} ${msg}`); };

const servidor = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: SERVIR, stdio: 'ignore' });
const esperar = async () => {
  for (let i = 0; i < 50; i++) {
    try { const r = await fetch(BASE + 'data/empresas.json'); if (r.ok) return; } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('servidor no levantó');
};

const browser = await chromium.launch();
try {
  await esperar();

  // --- 1. Layout en 360 y 390 px ---
  for (const width of [360, 390]) {
    const ctx = await browser.newContext({ viewport: { width, height: 740 }, isMobile: true, serviceWorkers: 'block' });
    const page = await ctx.newPage();
    const errores = [];
    page.on('pageerror', e => errores.push(e.message));
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.card');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(overflow <= 0, `${width}px: sin scroll horizontal en lista (exceso ${overflow}px)`);

    await page.locator('.card').first().click();
    await page.waitForSelector('#modalFicha[open]');
    const overflowFicha = await page.evaluate(() => {
      const d = document.querySelector('#modalFicha');
      return Math.max(d.scrollWidth - d.clientWidth, document.documentElement.scrollWidth - window.innerWidth);
    });
    check(overflowFicha <= 0, `${width}px: sin scroll horizontal en ficha (exceso ${overflowFicha}px)`);
    check(errores.length === 0, `${width}px: sin errores de JS (${errores.join(' | ') || 'ninguno'})`);
    await ctx.close();
  }

  // --- 2. Escape y esquemas de URL con datos hostiles ---
  const original = JSON.parse(readFileSync(join(SERVIR, 'data', 'empresas.json'), 'utf-8'));
  const base = original.empresas[0];
  const hostil = {
    ...base,
    id: 999999,
    slug: 'prueba-hostil',
    nombre: 'Evil <img src=x onerror="window.__xss=1">Hostil',
    actividad: 'x',
    direccion: '<b>dir</b>',
    telefono: '',
    email: '',
    web: 'javascript:window.__xss=2',
    instagram: 'javascript:window.__xss=3',
    facebook: '',
    linkedin: '',
    logo: 'x" onerror="window.__xss=4',
    membresias: [{ camara: 'CMS', rubro: 'Minería', url_ficha: '' }],
  };
  const inyectado = { ...original, empresas: [hostil, ...original.empresas] };

  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errores = [];
  page.on('pageerror', e => errores.push(e.message));
  await page.route('**/data/empresas.json', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(inyectado),
  }));
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.card');
  await page.waitForTimeout(300);

  const ejecuto = await page.evaluate(() => window.__xss);
  check(ejecuto === undefined, `payload en nombre/logo no se ejecuta en lista (__xss=${ejecuto})`);

  await page.locator('.card', { hasText: 'Hostil' }).first().click();
  await page.waitForSelector('#modalFicha[open]');
  await page.waitForTimeout(200);
  const ejecuto2 = await page.evaluate(() => window.__xss);
  check(ejecuto2 === undefined, `payload en ficha no se ejecuta (__xss=${ejecuto2})`);

  const jsHrefs = await page.evaluate(() =>
    [...document.querySelectorAll('#fichaContenido a[href]')].map(a => a.getAttribute('href'))
      .filter(h => /^javascript:/i.test(h)));
  check(jsHrefs.length === 0, `ningún link javascript: en la ficha (encontrados: ${jsHrefs.length})`);
  check(errores.length === 0, `sin errores de JS con datos hostiles (${errores.join(' | ') || 'ninguno'})`);
  await ctx.close();

  // --- 3. Impresión A4 de la lista ---
  const ctxPrint = await browser.newContext({ viewport: { width: 1000, height: 1200 }, serviceWorkers: 'block' });
  const pagePrint = await ctxPrint.newPage();
  await pagePrint.goto(BASE, { waitUntil: 'domcontentloaded' });
  await pagePrint.waitForSelector('.card');
  await pagePrint.emulateMedia({ media: 'print' });
  const pdf = join(CARPETA_PDF, 'lista-A4.pdf');
  await pagePrint.pdf({ path: pdf, format: 'A4', printBackground: true });
  check(readFileSync(pdf).length > 1000, `PDF A4 generado: ${pdf}`);
  await ctxPrint.close();
} catch (e) {
  fallos.push(String(e));
  console.log('FAIL excepción:', e);
} finally {
  await browser.close();
  servidor.kill();
}

console.log(fallos.length ? `\n${fallos.length} chequeo(s) fallaron` : '\nTodos los chequeos pasaron');
process.exit(fallos.length ? 1 : 0);
