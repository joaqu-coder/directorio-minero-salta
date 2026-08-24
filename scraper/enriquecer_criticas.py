#!/usr/bin/env python3
"""
Enriquecimiento de empresas críticas (3+ campos faltantes).
Intenta llenar: teléfono, email, sitio web, contacto nombre.
Fuentes: WHOIS, Google Search, LinkedIn, base SEGEMAR.
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Empresas críticas con indicaciones de búsqueda
CRITICAS_INDICADAS = {
    "POSCO Argentina SAU – Proyecto Sal de Oro": {
        "prioridad": "CRÍTICA",
        "proyecto": True,
        "multi": True,
        "pistas": ["POSCO", "Sal de Oro", "litio", "Argentina"]
    },
    "Rio Tinto – Proyecto Rincón": {
        "prioridad": "CRÍTICA",
        "proyecto": True,
        "multi": True,
        "pistas": ["Rio Tinto", "Rincón", "litio", "construcción"]
    },
    "Ganfeng Lithium – Proyecto Mariana": {
        "prioridad": "ALTA",
        "proyecto": True,
        "multi": True,
        "pistas": ["Ganfeng", "Mariana", "litio", "construcción"]
    },
    "Aldebaran Resources Inc.": {
        "prioridad": "ALTA",
        "proyecto": False,
        "multi": True,
        "pistas": ["Aldebaran", "Resources", "cobre", "oro"]
    },
    "Alpha Lithium – Proyecto Tolillar": {
        "prioridad": "ALTA",
        "proyecto": True,
        "multi": False,
        "pistas": ["Alpha Lithium", "Tolillar", "litio"]
    },
    "GASNOR S.A.": {
        "prioridad": "ALTA",
        "proyecto": False,
        "multi": True,
        "pistas": ["GASNOR", "energía", "gas"]
    }
}

def generar_pistas_busqueda(empresa: Dict) -> List[str]:
    """Genera pistas de búsqueda basadas en la empresa."""
    pistas = [
        empresa["nombre"],
        empresa["actividad"],
    ]

    # Si es proyecto minero, agregar términos específicos
    if "Proyecto" in empresa["nombre"]:
        pistas.extend(["Salta", "Argentina", "SEGEMAR"])

    # Si es multinacional
    if any(p in empresa["nombre"] for p in ["Inc.", "S.A.U", "SAU"]):
        pistas.extend(["Argentina", "oficina"])

    return [p for p in pistas if p and p.strip()]

def validar_whois(dominio: str) -> Optional[Dict]:
    """Simula validación WHOIS de dominio (requiere whois instalado)."""
    # TODO: Implementar con biblioteca whois
    return None

def generar_reporte_criticas(csv_path: str) -> None:
    """
    Analiza empresas críticas y genera pistas de enriquecimiento.
    """
    empresas = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        empresas = list(reader)

    campos_clave = ['telefono', 'email', 'sitio_web', 'contacto_nombre']

    criticas = []
    for emp in empresas:
        vacios = [c for c in campos_clave if not emp[c] or emp[c].strip() == '']
        if len(vacios) >= 3:
            criticas.append({
                'empresa': emp,
                'campos_vacios': vacios,
                'pistas': generar_pistas_busqueda(emp),
                'indicaciones': CRITICAS_INDICADAS.get(emp['nombre'], {})
            })

    # Generar JSON de investigación
    investigacion = {
        "fecha": "2026-08-24",
        "total_criticas": len(criticas),
        "empresas": [
            {
                "id": c['empresa']['id'],
                "nombre": c['empresa']['nombre'],
                "actividad": c['empresa']['actividad'],
                "campos_vacios": c['campos_vacios'],
                "pistas_busqueda": c['pistas'],
                "indicaciones": c['indicaciones'],
                "fuentes_recomendadas": recomendar_fuentes(c['empresa'])
            }
            for c in criticas
        ]
    }

    # Guardar en staging
    out = Path("data/staging/criticas_investigacion.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(investigacion, f, ensure_ascii=False, indent=2)

    print(f"✓ Reporte generado: {out}")
    print(f"  Total empresas críticas: {len(criticas)}")

def recomendar_fuentes(empresa: Dict) -> List[str]:
    """Recomienda fuentes de investigación por empresa."""
    nombre = empresa['nombre'].upper()
    fuentes = []

    # Proyectos mineros
    if 'PROYECTO' in nombre:
        fuentes.extend(['SEGEMAR', 'Portal Minería (Argentina)', 'Press releases'])

    # Multinacionales
    if any(s in nombre for s in ['INC.', 'S.A.U', 'SAU', 'LITHIUM', 'RESOURCES']):
        fuentes.extend(['Portal inversores empresa', 'LinkedIn empresa', 'Google Search'])

    # Empresas locales
    if 'SRL' in nombre or 'SAS' in nombre:
        fuentes.extend(['Cámara empresarial local', 'Google Maps', 'AFIP'])

    fuentes.extend(['RENAPER', 'Búsqueda directa'])
    return list(set(fuentes))

if __name__ == '__main__':
    generar_reporte_criticas('data/empresas.csv')
