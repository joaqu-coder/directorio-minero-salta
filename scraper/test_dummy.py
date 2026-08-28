import sqlite3
import os

DB_PATH = 'test_directorio.db'

# Limpiar si existe
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"🗑️  Archivo anterior {DB_PATH} eliminado")

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

# Crear schema ACTUAL (cámaras solamente)
db.executescript('''
CREATE TABLE empresas (
  id INTEGER PRIMARY KEY,
  nombre TEXT,
  nombre_norm TEXT UNIQUE,
  actividad TEXT,
  direccion TEXT,
  telefono TEXT,
  email TEXT,
  sitio_web TEXT,
  instagram TEXT,
  facebook TEXT,
  linkedin TEXT,
  logo_url TEXT,
  logo_origen TEXT,
  contacto_nombre TEXT,
  descripcion TEXT,
  ubicacion TEXT,
  cuit TEXT
);

CREATE TABLE membresias (
  empresa_id INTEGER,
  camara TEXT,
  rubro TEXT,
  url_ficha TEXT,
  PRIMARY KEY (empresa_id, camara, rubro),
  FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE cambios (
  id INTEGER PRIMARY KEY,
  empresa_id INTEGER,
  fecha TEXT,
  tipo TEXT,
  campo TEXT,
  valor_anterior TEXT,
  valor_nuevo TEXT,
  visto BOOLEAN
);

CREATE TABLE representantes (
  id INTEGER PRIMARY KEY,
  empresa_id INTEGER,
  nombre TEXT,
  nombre_norm TEXT,
  FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE INDEX idx_empresas_norm ON empresas(nombre_norm);
CREATE INDEX idx_membresias_empresa ON membresias(empresa_id);
''')

# Insertar 3 empresas dummy (cámaras)
db.execute('''
INSERT INTO empresas VALUES
  (1, 'Empresa CMS Test', 'empresa_cms_test', 'Minería', 'Calle 1', '1234567', 'cms@test.com', 'https://cms-test.com', NULL, NULL, NULL, NULL, 'CMS', 'Test CMS', 'Una empresa de prueba CMS', 'Salta', '20123456789'),
  (2, 'Empresa CAPEMISA Test', 'empresa_capemisa_test', 'Construcción', 'Calle 2', '7654321', 'cap@test.com', NULL, NULL, NULL, NULL, NULL, 'CAPEMISA', 'Test CAPEMISA', 'Una empresa de prueba CAPEMISA', 'Salta', '20987654321'),
  (3, 'Empresa UIS Test', 'empresa_uis_test', 'Servicios', 'Calle 3', '5555555', 'uis@test.com', NULL, NULL, NULL, NULL, NULL, 'UIS', 'Test UIS', 'Una empresa de prueba UIS', 'Salta', '20555555555')
''')

# Insertar membresias
db.execute('''
INSERT INTO membresias VALUES
  (1, 'CMS', 'Minería', 'https://cms/empresa-1'),
  (2, 'CAPEMISA', 'Construcción', 'https://capemisa/empresa-2'),
  (3, 'UIS', 'Servicios', 'https://uis/empresa-3')
''')

db.commit()

# Verificar
print("✅ Base de datos creada: test_directorio.db")
print(f"✅ Empresas totales: {db.execute('SELECT COUNT(*) FROM empresas').fetchone()[0]}")
print(f"✅ Membresias totales: {db.execute('SELECT COUNT(*) FROM membresias').fetchone()[0]}")

# Schema
print("\n📋 SCHEMA ACTUAL:")
print("=" * 60)
for row in db.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"):
    sql = row[0]
    if sql:
        print(f"\n{sql}")
print("\n" + "=" * 60)

# Verificar datos
print("\n📊 DATOS:")
print("\nEmpresas:")
for row in db.execute('SELECT id, nombre, nombre_norm FROM empresas'):
    print(f"  ID {row[0]}: {row[1]} (norm: {row[2]})")

print("\nMembresias:")
for row in db.execute('SELECT empresa_id, camara, rubro FROM membresias'):
    print(f"  Empresa {row[0]}: {row[1]} > {row[2]}")

db.close()

print("\n✨ LISTO para Paso B")
