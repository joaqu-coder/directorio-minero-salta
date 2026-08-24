# Empresas Sin Información Completa — Análisis y Plan de Enriquecimiento

**Fecha:** 2026-08-24  
**Total empresas:** 378  
**Sin información completa:** 184 (48.7%)

## 📊 Resumen de Déficit

| Campo | Empresas | % |
|---|---|---|
| Sitio web | 109 | 28.8% |
| Contacto (nombre) | 94 | 24.9% |
| Email | 45 | 11.9% |
| Teléfono | 38 | 10.1% |

## 🔴 Críticas — 27 empresas (3+ campos vacíos)

**20 ALTA prioridad** — Actores clave en minería de Salta:

1. **ARGENTUM LITHIUM S.A.** — Faltan: teléfono, email, sitio, contacto  
   ⚠️ *Empresa fantasma en registro — investigar si es activa*

2. **Abra Silver – Proyecto Diablillos** — Faltan: teléfono, email, sitio, contacto  
   💡 *Proyecto de plata en exploración — buscar contacto con JSA o holding*

3. **Aldebaran Resources Inc.** — Faltan: teléfono, email, contacto  
   💡 *Exploración cobre/oro/plata — empresa canadiense, probablemente tenga oficina en Salta*

4. **Alpha Lithium – Proyecto Tolillar** — Faltan: teléfono, email, contacto  
   💡 *Proyecto litio avanzado — buscar en base de datos de SEGEMAR*

5. **Corriente Argentina S.A. – Proyecto Taca Taca** — Faltan: teléfono, email, sitio, contacto  
   💡 *Exploración cobre — proyecto conocido en la región*

6. **ESTUDIO AGUILAR & ASOCIADOS** — Faltan: teléfono, email, sitio, contacto  
   💡 *Servicios jurídicos — buscar en directorios legales de Salta*

7. **FRIGORÍFICO BERMEJO SA / INVERSORA JURAMENTO S.A.** — Faltan: teléfono, email, sitio, contacto  
   💡 *Industria frigorífica — empresa importante del sector*

8. **GASNOR S.A.** — Faltan: teléfono, email, sitio, contacto  
   💡 *Energía — empresa nacional conocida, buscar oficina Salta*

9. **Ganfeng Lithium – Proyecto Mariana** — Faltan: teléfono, email, sitio, contacto  
   💡 *Proyecto litio EN CONSTRUCCIÓN (estado avanzado) — contacto crítico*

10. **JOFA S.A.** — Faltan: teléfono, email, sitio, contacto  
    💡 *Agroindustria/alimentos — empresa importante*

11. **Litica Resources – Proyecto Pozuelos** — Faltan: teléfono, email, contacto  
    💡 *Exploración litio — buscar en base SEGEMAR*

12. **MANUFACTURA DE LOS ANDES S.A.** — Faltan: teléfono, email, sitio, contacto  
    💡 *Ácido bórico — empresa productora conocida*

13. **Minera Santa Rita S.A. – Manufactura de Los Andes** — Faltan: teléfono, email, contacto  
    💡 *Producción boratos — relacionada con Manufactura de Los Andes*

14. **NOA LITHIUM BRINES S.A.** — Faltan: teléfono, email, sitio, contacto  
    💡 *Exploración litio — empresa regional*

15. **POSCO Argentina SAU – Proyecto Sal de Oro** — Faltan: teléfono, email, contacto  
    💡 *Proyecto litio EN CONSTRUCCIÓN (POSCO = coreana, empresa importante) — **CRÍTICA***

16. **Potasio y Litio de Argentina S.A.** — Faltan: teléfono, email, sitio, contacto  
    💡 *Exploración/construcción litio — empresa argentina conocida*

17. **REMSa S.A.** — Faltan: teléfono, email, contacto  
    ⚠️ *Sin descripción de actividad — investigar ramo*

18. **Rio Tinto – Proyecto Rincón** — Faltan: teléfono, email, contacto  
    💡 *Proyecto litio EN CONSTRUCCIÓN (Rio Tinto = multinacional) — **CRÍTICA***

19. **Silex Argentina SA – Proyecto El Quevar** — Faltan: teléfono, email, contacto  
    💡 *Exploración plata — proyecto conocido*

20. **TAMAR MINING S.A.** — Faltan: teléfono, email, sitio, contacto  
    💡 *Exploración cobre — empresa minera*

**7 MEDIA prioridad** — Otros sectores / empresas locales:

21-27: Agro San Pedro, Eramine Sudamerica SA, HIJOS DE SALVADOR MUÑOZ SRL, Hubaide Böhm & Asociados, Oxígeno Salta SRL, Ramón Nuñez, Recapados Santa Mónica

---

## 💡 Estrategia de Enriquecimiento

### Fase 1: Investigación de Proyectos Activos (SEMANA 1)

**Objetivo:** Completar teléfono/email/contacto de proyectos mineros en construcción.

1. **POSCO Argentina SAU – Proyecto Sal de Oro**  
   - Fuente: comunicado de prensa POSCO / portal inversores POSCO  
   - Buscar: contact de operaciones Argentina  

2. **Rio Tinto – Proyecto Rincón**  
   - Fuente: portal Rio Tinto Argentina / portal inversores  
   - Buscar: comunidad y relaciones públicas  

3. **Ganfeng Lithium – Proyecto Mariana**  
   - Fuente: base datos SEGEMAR / portal Ganfeng  
   - Buscar: operador local / JV partner  

### Fase 2: Empresas Multinacionales y Grandes (SEMANA 2)

**Objetivo:** Completar contactos y sitios web de empresas clave.

1. **Aldebaran Resources Inc.** — Canadiense  
   - Fuente: portal inversores Aldebaran + oficina Salta  
   - Pattern: `aldebaran.com` → `/argentina` / `/contact`  

2. **Litica Resources** — Exploración litio  
   - Fuente: base SEGEMAR + portal empresa  

3. **GASNOR S.A.** — Energía nacional  
   - Fuente: `gasnor.com.ar` + directorio público  

### Fase 3: Enriquecimiento Local (SEMANA 3)

**Objetivo:** Completar campos de empresas de servicios, agroindustria y locales.

- Contactar directamente cámaras locales (CMS, CAPEMISA, UIS)  
- Validar en bases públicas: AFIP, RENAPER, SEGEMAR  
- Buscar en Google Maps + LinkedIn (empresa + ubicación)  

---

## 📋 Checklist de Acción

### Campo "sitio_web" (109 empresas sin)
- [ ] Rastrear dominios WHOIS con nombre empresa + Salta  
- [ ] Buscar en Google + LinkedIn (perfil empresa)  
- [ ] Nota: ~20% pueden no tener sitio oficial → registrar `NULL` explícitamente  

### Campo "email" (45 empresas sin)
- [ ] WHOIS + `@` de dominio si existe  
- [ ] Google: `site:empresa.com.ar email` / `contacto`  
- [ ] LinkedIn: empresa → "Contact Info"  

### Campo "telefono" (38 empresas sin)
- [ ] Búsqueda Google Maps (nombre + Salta)  
- [ ] Directorio de cámaras (CMS, CAPEMISA, UIS)  
- [ ] Llamada directa a cámara si empresa es miembro  

### Campo "contacto_nombre" (94 empresas sin)
- [ ] LinkedIn: empresa → filtrar "Argentina" + rol relevante  
- [ ] Sitio oficial → "Quiénes somos" / "Equipo"  
- [ ] Contactar cámara para referencia  

---

## 🔧 Automatización Sugerida

```bash
# 1. Enriquecimiento vía Google Search + scraping
python3 scraper/enriquecer_google.py data/candidatos_revision.csv

# 2. Validación de dominios + DNS
python3 scraper/validar_dominios.py data/empresas.csv

# 3. LinkedIn scraping (cuidado: ToS)
python3 scraper/enriquecer_linkedin.py data/empresas.csv --contacto

# 4. Generar informe de progreso
python3 scraper/generar_informe_enriquecimiento.py
```

---

## 📞 Contactos Recomendados para Investigación

| Cámara | Contact | Línea |
|---|---|---|
| **CMS (Cámara Minería)** | Presidencia | Solicitar nómina actualizada + teléfonos |
| **CAPEMISA** | Info / Membresía | Validar campos vacíos |
| **UIS** | Directorio | Enriquecimiento de empresas |
| **SEGEMAR** | Base de Datos Proyectos | Minería activa en Salta |

---

## ⚡ Próximos Pasos Inmediatos

1. **Esta semana:** Investigar 5 proyectos mineros críticos (POSCO, Rio Tinto, Ganfeng, Aldebaran, Alpha Lithium)
2. **Script de validación:** Crear herramienta para detectar dominios válidos vía WHOIS
3. **Contacto cámaras:** Solicitar actualización de base de datos + campos faltantes
4. **PR con enriquecimiento:** Documentar fuentes de cada empresa + fecha investigación

---

*Generado por análisis automático. Requiere validación manual para cada empresa.*
