# -*- coding: utf-8 -*-
"""Calcula un ajuste de gris por logo para que todos se vean con la misma
tonalidad y contraste en la app.

Para cada empresa con logo mide la luminancia mediana m de su contenido
(píxeles opacos y no blancos) y la lleva a la mediana T de todos los logos,
manteniendo el blanco en blanco. Salida: data/logos_ajuste.json
{"<id>": {"b": .., "c": .., "g": ..}}
Los logos sin contenido medible (p. ej. blancos) no entran: quedan con el
filtro base y, si no se ven, la app muestra el nombre.

Uso:
    python scraper/ajustar_logos.py                 # solo logos locales (data/logos)
    python scraper/ajustar_logos.py --descargar     # también descarga los remotos
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
LADO = 64
MIN_TINTA = 0.03  # fracción mínima de píxeles con contenido para medir


def cargar_imagen(logo, descargar):
    if logo.startswith('data/'):
        ruta = os.path.join(RAIZ, logo)
        if not os.path.exists(ruta):
            return None
        with open(ruta, 'rb') as f:
            datos = f.read()
    elif descargar and logo.startswith('http'):
        req = urllib.request.Request(logo, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                datos = r.read()
        except Exception:
            return None
    else:
        return None
    try:
        return Image.open(io.BytesIO(datos)).convert('RGBA').resize((LADO, LADO))
    except Exception:
        return None  # SVG u otro formato que PIL no abre


def medir(img):
    """Luminancias (0-255) de los píxeles con contenido visible."""
    lums = []
    for r, g, b, a in img.getdata():
        if a > 40:
            lum = (r + g + b) / 3
            if lum < 235:  # descarta fondo blanco o casi blanco
                lums.append(lum)
    if len(lums) < MIN_TINTA * LADO * LADO:
        return None
    m = statistics.median(lums)
    sd = statistics.pstdev(lums)
    return {'m': m, 'sd': max(sd, 1.0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--descargar', action='store_true')
    args = ap.parse_args()

    with open(EMPRESAS, encoding='utf-8') as f:
        empresas = json.load(f)['empresas']

    medidas = {}
    for e in empresas:
        if not e.get('logo'):
            continue
        img = cargar_imagen(e['logo'], args.descargar)
        if img is None:
            continue
        r = medir(img)
        if r:
            medidas[str(e['id'])] = r

    if not medidas:
        print('Sin logos medibles', file=sys.stderr)
        return 1

    T = statistics.median(v['m'] for v in medidas.values())

    # Transformación que deja el blanco en blanco (sin cajas grises de fondo):
    # L' = 255 - g*(255 - L). En CSS: brightness(b) contrast(c) con b*c = g
    # y c = 1 - 255*(1-g)/128. Se mide la distancia de la tinta al blanco.
    ajuste = {}
    for id_, v in medidas.items():
        g = min(max((255 - T) / (255 - v['m']), 0.7), 2.0)
        c = 1 - 255 * (1 - g) / 128
        b = g / c
        ajuste[id_] = {'b': round(b, 3), 'c': round(c, 3), 'g': round(g, 3)}

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(ajuste, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)

    print(f'Medidos: {len(medidas)} | T={T:.1f} -> {SALIDA}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
