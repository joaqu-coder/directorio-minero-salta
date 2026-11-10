# -*- coding: utf-8 -*-
"""Aloja los logos remotos en data/logos/ y calcula un ajuste de gris por
logo, para que todos se trabajen y se vean de la misma manera.

Para cada empresa con logo:
  1. Si es remoto y se pide --alojar, lo descarga a data/logos/<id>.<ext>.
  2. Mide la imagen (fondo y tinta) y deriva un filtro propio:
       L' = a*L + o
     que lleva el fondo a blanco (L * 255/B) y la tinta a la mediana común T,
     manteniendo el blanco en blanco. Los SVG se alojan pero no se miden.

Salida: data/logos_ajuste.json  {"<id>": {"src": "data/logos/<id>.png",
                                          "a": .., "o": ..}}
La app usa "src" si existe y aplica el filtro si hay "a" y "o".

Uso:
    python scraper/ajustar_logos.py                # solo logos ya locales
    python scraper/ajustar_logos.py --alojar       # descarga y aloja los remotos
"""
import argparse
import io
import json
import os
import statistics
import sys
import urllib.request

from PIL import Image

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EMPRESAS = os.path.join(RAIZ, 'data', 'empresas.json')
SALIDA = os.path.join(RAIZ, 'data', 'logos_ajuste.json')
CARPETA = os.path.join(RAIZ, 'data', 'logos')
LADO = 64
FALLOS = []  # (url, motivo) de cada descarga fallida
MIN_TINTA = 0.03  # fracción mínima de píxeles con contenido para medir


def leer_bytes(logo, alojar):
    """Bytes del logo: archivo local, o descarga si es remoto y se pidió alojar."""
    if logo.startswith('data/'):
        ruta = os.path.join(RAIZ, logo)
        if os.path.exists(ruta):
            with open(ruta, 'rb') as f:
                return f.read()
        return None
    if alojar and logo.startswith('http'):
        return descargar(logo)
    return None


def descargar(url):
    """Descarga con huella TLS de navegador (curl_cffi), que los sitios con WAF
    aceptan; si no está instalado, cae a urllib. Devuelve None si falla."""
    try:
        from curl_cffi import requests as cffi
        r = cffi.get(url, impersonate='chrome', timeout=25, allow_redirects=True)
        if r.status_code == 200 and r.content:
            return r.content
        motivo = f'HTTP {r.status_code}'
    except ImportError:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()
        except Exception as ex:
            motivo = type(ex).__name__
    except Exception as ex:
        motivo = type(ex).__name__
    FALLOS.append((url, motivo))
    return None


def extension(datos):
    if datos[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if datos[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if datos[:4] == b'GIF8':
        return 'gif'
    if datos[:4] == b'RIFF' and datos[8:12] == b'WEBP':
        return 'webp'
    head = datos[:300].lstrip().lower()
    if head.startswith(b'<svg') or (head.startswith(b'<?xml') and b'<svg' in datos[:2000].lower()):
        return 'svg'
    return None


def rasterizar(datos):
    try:
        return Image.open(io.BytesIO(datos)).convert('RGBA').resize((LADO, LADO))
    except Exception:
        return None


def medir(img):
    """Color de fondo (borde opaco) y mediana de la tinta, ya con el fondo blanco.

    Si el fondo es gris claro (p. ej. #ebebeb), se escala para que sea blanco
    (L * 255/B). Así el fondo no se ve como caja gris y la tinta conserva sus
    proporciones.
    """
    px = list(img.getdata())
    w = LADO
    borde = [px[i] for i in range(len(px))
             if i < w or i >= len(px) - w or i % w in (0, w - 1)]
    opacos = [(r + g + b) / 3 for r, g, b, a in borde if a > 200]
    B = statistics.median(opacos) if len(opacos) > 0.8 * len(borde) else 255.0
    if B < 180:  # el borde no es un fondo claro: no escalar
        B = 255.0
    A1 = 255.0 / B
    umbral = min(235.0, B - 12)  # tinta = todo lo que no es fondo
    lums = []
    for r, g, b, a in px:
        if a > 40:
            lum = (r + g + b) / 3
            if lum < umbral:
                lums.append(lum)
    if len(lums) < MIN_TINTA * LADO * LADO:
        return None
    return {'m': statistics.median(lums) * A1, 'A1': A1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--alojar', action='store_true',
                    help='descarga los logos remotos a data/logos/')
    args = ap.parse_args()

    with open(EMPRESAS, encoding='utf-8') as f:
        empresas = json.load(f)['empresas']

    os.makedirs(CARPETA, exist_ok=True)
    entradas = {}  # id -> {"src": ..., "medida": {...} | None, "nuevo": bool}
    for e in empresas:
        logo = e.get('logo')
        if not logo:
            continue
        datos = leer_bytes(logo, args.alojar)
        if datos is None:
            continue
        ext = extension(datos)
        if ext is None:
            continue
        src, nuevo = logo, False
        if logo.startswith('http'):
            src = f'data/logos/{e["id"]}.{ext}'
            with open(os.path.join(RAIZ, src), 'wb') as f:
                f.write(datos)
            nuevo = True
        img = rasterizar(datos) if ext != 'svg' else None
        medida = medir(img) if img is not None else None
        entradas[str(e['id'])] = {'src': src, 'medida': medida, 'nuevo': nuevo}

    medidas = {k: v['medida'] for k, v in entradas.items() if v['medida']}
    if not medidas:
        print('Sin logos medibles', file=sys.stderr)
        return 1

    T = statistics.median(v['m'] for v in medidas.values())

    # Por logo: el fondo va a blanco (A1) y la tinta a la mediana común T,
    # manteniendo el blanco en blanco:
    #   L' = 255 - g*(255 - A1*L) = a*L + o   con a = g*A1, o = 255*(1-g)
    # La app lo aplica como un filtro SVG (feComponentTransfer lineal).
    salida = {}
    for id_, v in entradas.items():
        fila = {'src': v['src']}
        if v['medida']:
            m = v['medida']
            g = min(max((255 - T) / (255 - m['m']), 0.7), 2.0)
            fila['a'] = round(g * m['A1'], 4)
            fila['o'] = round(255 * (1 - g), 2)
        salida[id_] = fila

    # No perder entradas de corridas anteriores (p. ej. una corrida sin --alojar
    # no descarga los remotos y no debe borrarlos).
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding='utf-8') as f:
            for id_, fila in json.load(f).items():
                salida.setdefault(id_, fila)

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)

    if FALLOS:
        from collections import Counter
        por_motivo = Counter(m for _, m in FALLOS)
        print(f'Descargas fallidas: {len(FALLOS)} {dict(por_motivo)}', file=sys.stderr)
        for url, motivo in FALLOS[:5]:
            print(f'  {motivo}: {url}', file=sys.stderr)
    nuevos = sum(1 for v in entradas.values() if v['nuevo'])
    print(f'Medidos: {len(medidas)} de {len(entradas)} | T={T:.1f} | '
          f'alojados ahora: {nuevos} -> {SALIDA}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
