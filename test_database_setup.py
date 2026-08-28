#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime

DB_PATH = 'test_directorio.db'

print("=" * 50)
print("🧪 TESTING PI SALTA INTEGRATION")
print("=" * 50)

# ===========================================
# PASO B: Crear tabla unidades_inmobiliarios
# ===========================================
print("\n📋 PASO B: Crear tabla unidades_inmobiliarios...")
db = sqlite3.connect(DB_PATH)

db.executescript('''
CREATE TABLE IF NOT EXISTS unidades_inmobiliarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parque TEXT NOT NULL CHECK (parque IN ('GÜEMES', 'SALTA')),
  numero TEXT NOT NULL,
  superficie_m2 REAL,
  titularidad TEXT,
  estado TEXT,
  UNIQUE(parque, numero)
);
CREATE INDEX IF NOT EXISTS idx_unidades_parque ON unidades_inmobiliarios(parque);
''')
print("✓ Tabla unidades_inmobiliarios creada")
print("✅ PASO B completado")

# ===========================================
# PASO C: Migrar membresias (recrear tabla)
# ===========================================
print("\n📋 PASO C: Migrar membresias (recrear tabla)...")

print("  1️⃣ Backup membresias_old...")
db.execute('CREATE TABLE IF NOT EXISTS membresias_old AS SELECT * FROM membresias WHERE 1=0')
db.execute('INSERT INTO membresias_old SELECT * FROM membresias')

print("  2️⃣ Drop tabla vieja...")
db.execute('DROP TABLE membresias')

print("  3️⃣ Crear tabla NUEVA (bifurcada)...")
db.executescript('''
CREATE TABLE membresias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER NOT NULL,
  camara TEXT,
  rubro TEXT,
  url_ficha TEXT,
  unidad_id INTEGER,
  FOREIGN KEY (empresa_id) REFERENCES empresas(id),
  FOREIGN KEY (unidad_id) REFERENCES unidades_inmobiliarios(id),
  CHECK (
    (camara IS NOT NULL AND unidad_id IS NULL) OR
    (camara IS NULL AND unidad_id IS NOT NULL)
  )
);
CREATE INDEX idx_membresias_empresa ON membresias(empresa_id);
CREATE INDEX idx_membresias_unidad ON membresias(unidad_id);
''')

print("  4️⃣ Repoblar desde backup...")
db.execute('''
INSERT INTO membresias (empresa_id, camara, rubro, url_ficha)
  SELECT empresa_id, camara, rubro, url_ficha FROM membresias_old
''')
count = db.execute('SELECT COUNT(*) FROM membresias').fetchone()[0]
print(f"  ✓ {count} registros repoblados")

print("  5️⃣ Limpiar backup...")
db.execute('DROP TABLE membresias_old')

db.commit()
print("✓ Migración completada")
print(f"✓ Membresias totales: {count}")
print("✅ PASO C completado")

# ===========================================
# PASO D: Cargar datos PI Salta DUMMY
# ===========================================
print("\n📋 PASO D: Cargar datos PI Salta DUMMY...")

print("  1️⃣ Limpiar datos previos...")
db.execute('DELETE FROM membresias WHERE unidad_id IS NOT NULL')
db.execute('DELETE FROM empresas WHERE id > 3')
db.execute('DELETE FROM unidades_inmobiliarios')
db.commit()

# DATOS DUMMY
empresas_dummy = [
    {'nombre': 'SALTA STONE SAS', 'rubro': 'Fabricación de Mármol', 'cuit': '30717584054', 'direccion': 'Av. X 123', 'telefono': '387123456', 'email': 'info@saltastone.com', 'contacto': 'Juan Pérez'},
    {'nombre': 'TEMET S.R.L', 'rubro': 'Servicios Eléctricos', 'cuit': '20128030698', 'direccion': 'Av. Y 456', 'telefono': '387654321', 'email': 'temet@test.com', 'contacto': 'Carlos López'},
    {'nombre': 'TOMASINI MARCELA', 'rubro': 'Servicios', 'cuit': '27208765952', 'direccion': 'Av. Z 789', 'telefono': '387999999', 'email': 'tomasini@test.com', 'contacto': 'Marcela Tomasini'},
    {'nombre': 'PALLETS SAN ANTONIO', 'rubro': 'Elaboración de Pallets', 'cuit': '30710866070', 'direccion': 'Av. Delgadillo 2278', 'telefono': '387473107', 'email': 'pallets@test.com', 'contacto': 'Juan Anderson'},
    {'nombre': 'SEPELIOS RIGO S.R.L', 'rubro': 'Fabricación de Ataúdes', 'cuit': '23072411889', 'direccion': 'Av. Delgadillo 2270', 'telefono': '4393681', 'email': 'rigo@test.com', 'contacto': 'Emilce'},
]

lotes_dummy = [
    {'empresa': 'SALTA STONE SAS', 'lote': '7', 'matricula': '172590', 'superficie': '1000.18', 'titularidad': 'SALTA STONE S.A.S', 'estado': 'EN ACTIVIDAD'},
    {'empresa': 'TEMET S.R.L', 'lote': '69', 'matricula': '151563', 'superficie': '3545', 'titularidad': 'Armando Galloni', 'estado': 'EN ACTIVIDAD'},
    {'empresa': 'TOMASINI MARCELA', 'lote': '69', 'matricula': '151563', 'superficie': '2835', 'titularidad': 'TOMASINI MARCELA', 'estado': 'EN ACTIVIDAD'},
    {'empresa': 'PALLETS SAN ANTONIO', 'lote': '6', 'matricula': '172586', 'superficie': '4991.96', 'titularidad': 'ENTE GENERAL DE PARQUES', 'estado': 'EN ACTIVIDAD'},
    {'empresa': 'SEPELIOS RIGO S.R.L', 'lote': '6', 'matricula': '172591', 'superficie': '2000.71', 'titularidad': 'ENTE GENERAL DE PARQUES', 'estado': 'EN ACTIVIDAD'},
]

print("  2️⃣ Insertar lotes únicos...")
lotes_unicos = {}
for lote in lotes_dummy:
    key = lote['lote']  # solo lote, no (lote, matricula)
    if key not in lotes_unicos:
        lotes_unicos[key] = lote

for lote_num, lote_data in lotes_unicos.items():
    db.execute('''
        INSERT INTO unidades_inmobiliarios (parque, numero, superficie_m2, titularidad, estado)
        VALUES (?, ?, ?, ?, ?)
    ''', ('SALTA', lote_num, float(lote_data['superficie']), lote_data['titularidad'], lote_data['estado']))
    print(f"    ✓ Lote {lote_num}")

db.commit()

print("  3️⃣ Insertar empresas PI Salta...")
max_id = 3
for idx, empresa in enumerate(empresas_dummy):
    empresa_id = max_id + idx + 1
    nombre = empresa['nombre']
    nombre_norm = nombre.lower().strip()
    rubro = empresa['rubro']

    lote_row = next((l for l in lotes_dummy if l['empresa'] == nombre), None)

    db.execute('''
        INSERT INTO empresas (id, nombre, nombre_norm, actividad, direccion,
                              telefono, email, contacto_nombre, ubicacion, cuit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        empresa_id,
        nombre,
        nombre_norm,
        rubro,
        empresa['direccion'],
        empresa['telefono'],
        empresa['email'],
        empresa['contacto'],
        'Parque Industrial Salta',
        empresa['cuit']
    ))

    unidad_id = None
    if lote_row:
        u = db.execute(
            'SELECT id FROM unidades_inmobiliarios WHERE parque=? AND numero=?',
            ('SALTA', lote_row['lote'])
        ).fetchone()
        if u:
            unidad_id = u[0]

    if unidad_id:
        db.execute('''
            INSERT INTO membresias (empresa_id, unidad_id, rubro)
            VALUES (?, ?, ?)
        ''', (empresa_id, unidad_id, rubro))
        print(f"    ✓ {nombre} → Lote {lote_row['lote']}")

db.commit()

print("\n  📊 RESULTADOS:")
empresas_count = db.execute('SELECT COUNT(*) FROM empresas').fetchone()[0]
membresias_count = db.execute('SELECT COUNT(*) FROM membresias').fetchone()[0]
unidades_count = db.execute('SELECT COUNT(*) FROM unidades_inmobiliarios').fetchone()[0]
print(f"    Empresas totales: {empresas_count}")
print(f"    Membresias totales: {membresias_count}")
print(f"    Unidades (lotes): {unidades_count}")

print("\n  ⚠️  CONFLICTOS:")
conflictos_query = db.execute('''
    SELECT unidad_id, COUNT(*) as cant
    FROM membresias
    WHERE unidad_id IS NOT NULL
    GROUP BY unidad_id
    HAVING cant > 1
''')
has_conflicts = False
for row in conflictos_query:
    has_conflicts = True
    empresas_en_lote = db.execute('''
        SELECT e.nombre FROM empresas e
        JOIN membresias m ON e.id = m.empresa_id
        WHERE m.unidad_id = ?
    ''', (row[0],)).fetchall()
    lote_num = db.execute('SELECT numero FROM unidades_inmobiliarios WHERE id=?', (row[0],)).fetchone()[0]
    print(f"    Lote {lote_num}: {', '.join([e[0] for e in empresas_en_lote])}")

if not has_conflicts:
    print("    (ninguno)")

print("\n✓ Carga completada")
print("✅ PASO D completado")

# ===========================================
# PASO E: Regenerar empresas.json
# ===========================================
print("\n📋 PASO E: Regenerar empresas_dummy.json...")

db.row_factory = sqlite3.Row
empresas_dict = {}
for row in db.execute('SELECT * FROM empresas'):
    empresa_id = row['id']
    slug = row['nombre_norm'].replace(' ', '-')

    membresias = []
    for m in db.execute('SELECT * FROM membresias WHERE empresa_id = ?', (empresa_id,)):
        mem = {
            'id': m['id'],
            'camara': m['camara'],
            'rubro': m['rubro'],
            'url_ficha': m['url_ficha'],
            'unidad_id': m['unidad_id'],
        }

        if m['unidad_id']:
            u = db.execute('SELECT * FROM unidades_inmobiliarios WHERE id = ?', (m['unidad_id'],)).fetchone()
            if u:
                mem['_parque'] = u['parque']
                mem['_lote'] = u['numero']
                mem['_matricula'] = u['numero']
                mem['_superficie'] = f"{u['superficie_m2']} m²" if u['superficie_m2'] else None
                mem['_titularidad'] = u['titularidad']
                mem['_estado'] = u['estado']

        membresias.append(mem)

    empresas_dict[empresa_id] = {
        'id': empresa_id,
        'slug': slug,
        'nombre': row['nombre'],
        'actividad': row['actividad'],
        'direccion': row['direccion'],
        'telefono': row['telefono'],
        'email': row['email'],
        'web': row['sitio_web'],
        'instagram': row['instagram'],
        'facebook': row['facebook'],
        'contacto': row['contacto_nombre'],
        'descripcion': row['descripcion'],
        'ubicacion': row['ubicacion'],
        'membresias': membresias
    }

output = {
    'generado': datetime.now().isoformat(),
    'empresas': list(empresas_dict.values())
}

with open('data/empresas_dummy.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✓ empresas_dummy.json generado")
print(f"✓ Empresas exportadas: {len(output['empresas'])}")
print(f"✓ Tamaño: {len(json.dumps(output)) / 1024:.1f} KB")
print("✅ PASO E completado")

# ===========================================
# PASO F: Verificar estructura JSON
# ===========================================
print("\n📋 PASO F: Verificar estructura empresas_dummy.json...")

with open('data/empresas_dummy.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"✓ JSON válido")
print(f"✓ Total empresas: {len(data['empresas'])}")
print(f"✓ Generado: {data['generado']}")

print("\n📊 EMPRESAS CARGADAS:")
for emp in data['empresas']:
    print(f"\n  ID {emp['id']}: {emp['nombre']}")
    print(f"    Slug: {emp['slug']}")
    print(f"    Ubicación: {emp['ubicacion']}")
    print(f"    Membresias: {len(emp['membresias'])}")
    for mem in emp['membresias']:
        if mem['camara']:
            print(f"      - {mem['camara']} > {mem['rubro']}")
        elif mem['unidad_id']:
            print(f"      - 🏭 {mem['_parque']} > Lote {mem['_lote']} ({mem['_estado']})")

print("\n✓ Estructura correcta")
print("✅ PASO F completado")

db.close()

print("\n" + "=" * 50)
print("✨ TODOS LOS PASOS COMPLETADOS")
print("=" * 50)
