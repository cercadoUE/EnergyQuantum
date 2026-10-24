# Plataforma web EnergyQuantum Perú — informe de implementación

## 1. Resumen

Se construyó una plataforma web nueva sobre el proyecto existente, sin reemplazar
los solvers ni la capa de datos reales. El primer acceso (`/mapa`) muestra el mapa
real del Perú con fondo claro, líneas coloreadas por tensión, subestaciones,
centrales y etiquetas. La aplicación Streamlit se conserva como versión legada.

Stack: **React 19 + Vite 6 + TypeScript + MapLibre GL JS + React Router +
Recharts + Lucide**, con una **API FastAPI** que reutiliza `select_subnet`,
`build_instance`, `Objective`, los solvers clásicos, QAOA y el simulador de
fallas ya existentes.

## 2. Decisiones de diseño

- No se empezó de cero: la API importa los módulos Python del proyecto y los
  activos del mapa se generan desde `data/processed/sein_network.json`.
- Se mantiene la separación de procedencia: **OFICIAL**, **DERIVADO**,
  **VALIDADO** y **SIMULADO**.
- Solo se crean aristas cuando los extremos explícitos (`NODO_SALIDA`,
  `NODO_LLEGADA`) quedan resueltos. La proximidad solo desempata identidades.
- La demanda sigue siendo un supuesto **SIMULADO**; la generación se fija en 0
  porque no existe despacho por subestación.
- COES **no** se automatiza: `coes_validated_edges = 0` en todo el snapshot.
- El fondo del mapa es Esri World Light Gray Base + Reference (sin API key) y
  las etiquetas usan la fuente pública de demotiles de MapLibre.
- En móvil el resumen del mapa se colapsa en una píldora y el control de capas
  se abre como panel lateral, para que el mapa real quede visible.

## 3. Archivos creados o modificados

### Backend

| Archivo | Tipo | Contenido |
| --- | --- | --- |
| `api/main.py` | creado | API FastAPI, modelos Pydantic, reutilización de solvers, particiones, fallas y fuentes |
| `api/__init__.py` | creado | Paquete de la API |
| `scripts/export_frontend_data.py` | creado | Exporta resumen, componentes, estaciones, GeoJSON y experimento; normaliza tensiones |
| `requirements.txt` | modificado | Añadidos `fastapi==0.162.0` y `pydantic==2.14.1` |

### Frontend

| Archivo | Contenido |
| --- | --- |
| `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html` | Configuración, dependencias, proxy `/api` y build |
| `frontend/src/main.tsx`, `App.tsx` | Arranque y rutas |
| `frontend/src/components/AppShell.tsx` | Sidebar, topbar, búsqueda global y estado de API |
| `frontend/src/components/MapCanvas.tsx` | Mapa MapLibre: capas, filtros, popups, subred, partición y fallas |
| `frontend/src/components/ui.tsx` | Panel, badges, tarjetas, toggles, estados de carga/error |
| `frontend/src/pages/MapPage.tsx` | Landing con mapa real, hero, capas, leyenda, drawer y barra de estado |
| `frontend/src/pages/NetworkPage.tsx` | Explorador de estaciones y líneas |
| `frontend/src/pages/SubnetsPage.tsx` | Componentes y subredes verificadas |
| `frontend/src/pages/OptimizationPage.tsx` | Configuración y resultados clásicos/QAOA |
| `frontend/src/pages/FailuresPage.tsx` | Simulación de fallas sobre la topología |
| `frontend/src/pages/ComparePage.tsx` | Comparación reproducible desde `experiment.json` |
| `frontend/src/pages/SyntheticPage.tsx` | Laboratorio sintético separado |
| `frontend/src/pages/SourcesPage.tsx` | Fuentes, manifiesto, etiquetas y limitaciones |
| `frontend/src/lib/api.ts`, `types.ts`, `format.ts`, `colors.ts` | Cliente API, tipos, formato y colores por tensión |
| `frontend/src/styles.css` | Sistema visual completo y responsive |
| `frontend/public/data/*` | Activos estáticos generados |

### Activos generados

`summary.json`, `components.json`, `stations-index.json`, `experiment.json`,
`manifest.json`, `map/stations.geojson`, `map/lines.geojson`,
`map/edges.geojson` y `map/generation.geojson`.

### Documentación

- `README.md`: sección nueva de la plataforma web y comandos.
- `docs/WEB_PLATFORM_REPORT.md`: este informe.

## 4. Datos descargados y procesados

Snapshot oficial de OSINERGMIN usado por la plataforma:

- Servicio: `MapaSEIN_Operacion` (ArcGIS REST).
- Descarga: `2026-10-24T18:18:45+00:00`.
- Capas oficiales: **17** (subestaciones 33/60/138/220/500 kV, líneas
  33/60/138/220/500 kV y siete capas de generación).
- Registros de estaciones: **967** → **685** tras fusionar 282 duplicados con
  radio de 0.75 km.
- Registros de líneas: **986** → **977** tras eliminar 9 duplicados.
- Centrales de generación: **246**.
- Registros omitidos: **10** (sin geometría o sin datos mínimos).

Activos estáticos regenerados con `scripts/export_frontend_data.py`; las
tensiones se redondean a dos decimales para evitar ruido (`22.89999962` → `22.9`).

## 5. Conexiones verificadas y topología

- Estaciones: **685**; en el grafo verificado: **502**.
- Líneas: **977**; verificadas: **618**; no verificadas: **359**.
- Aristas agregadas con extremos explícitos: **501**.
- Componentes con aristas: **48**; mayor componente: **153 nodos**.
- Aristas validadas por COES: **0**.
- Comprobaciones: 0 IDs duplicados, 0 pares duplicados, 0 auto-lazos,
  0 geometrías inválidas y 16 líneas no verificadas por extremos faltantes.

Una conexión verificada significa que los atributos explícitos de extremos
coinciden; **no** certifica suministro ni operación.

## 6. Funcionalidades

1. **Mapa nacional** (`/mapa`): mapa real, capas conmutables, filtros por
   tensión y departamento, búsqueda, drawer de subestación, coordenadas y zoom.
2. **Explorador de red** (`/red`): estaciones y líneas con búsqueda y detalle.
3. **Subredes verificadas** (`/subredes`): componentes, subredes de 4–12 nodos,
   puentes, exportación y envío a optimización.
4. **Optimización** (`/optimizacion`): Exacto, Búsqueda local, Kernighan–Lin y
   QAOA; H, corte, factibilidad, tiempos, partición y gráficos.
5. **Simulador de fallas** (`/fallas`): retiro de aristas, comparación
   antes/después y mapa de la partición resultante.
6. **Comparación** (`/comparacion`): lee `experiment.json` y tolera API caída.
7. **Red sintética** (`/sintetico`): 4–12 nodos, grafo normalizado, partición
   por colores y ejecución de los cuatro métodos.
8. **Fuentes y metodología** (`/fuentes`): manifiesto, etiquetas, pipeline y
   limitaciones; tolera API caída con datos estáticos.

## 7. Pruebas ejecutadas

| Prueba | Comando | Resultado |
| --- | --- | --- |
| Suite Python | `..\.venv\Scripts\python.exe -m pytest -q` | **48 passed, 1 skipped** (20.9 s) |
| Tipos TypeScript | `npm run typecheck` | Sin errores |
| Build de producción | `npm run build` | Correcto; chunks separados (`maplibre` 1.05 MB, `charts` 395 kB, `index` 333 kB, CSS 112 kB) |
| Verificación visual | Playwright en `/mapa`, `/red`, `/subredes`, `/optimizacion`, `/fallas`, `/comparacion`, `/sintetico`, `/fuentes` | Sin errores de consola |
| Responsive | 1536, 900 y 390 px | Sin desbordamiento horizontal; sidebar, hero y capas adaptados |
| Ejecución real desde UI | Optimización y fallas | Resultados coherentes con la API |
| Ejecución sintética desde UI | 12 nodos, cuatro métodos | Partición 6/6 y 3 aristas de corte |

## 8. Resultados

### Subred real verificada

Componente 1 de La Libertad: **6 nodos, 6 aristas, 2 puentes**, 51.034 km,
tensiones 60/138/220 kV.

| Método | H | Corte (km) | Tiempo | Factible |
| --- | --- | --- | --- | --- |
| Exacto | 0.23219814241486067 | 11.85 | 2.57 ms | Sí |
| Búsqueda local | 0.23219814241486067 | 11.85 | 77.28 ms | Sí |
| Kernighan–Lin | 0.23219814241486067 | 11.85 | 2.12 ms | Sí |
| QAOA | 0.23219814241486067 | 11.85 | 180.82 ms | Sí |

Los cuatro métodos coinciden en el óptimo de esta instancia. La validación
marca conectividad correcta, pero `generation_adequate = false` porque la
generación se fija en 0 (supuesto, no un resultado eléctrico).

### Falla de ejemplo

Retirar `ed_8e3c8a73870e` en la misma subred:

- Aristas activas: **6 → 5**.
- Componentes: **1 → 2**.
- Nodos aislados: **0 → 1**.
- Longitud activa: **51.034 → 44.824 km**.

### Red sintética (12 nodos)

| Método | H | Corte | Tiempo | Factible |
| --- | --- | --- | --- | --- |
| Exacto | 0.22524 | 9.00 | 255 ms | Sí |
| Búsqueda local | 0.22524 | 9.00 | 71 ms | Sí |
| Kernighan–Lin | 0.22524 | 9.00 | 6 ms | Sí |
| QAOA | 0.22524 | 9.00 | 569 ms | Sí |

Los tiempos varían según la máquina y la carga. No se afirma ventaja cuántica:
en estas instancias pequeñas los métodos clásicos y QAOA llegan al mismo
óptimo, y QAOA es más lento.

## 9. Limitaciones

- COES no se consulta de forma automatizada; **ninguna arista está validada por
  COES**.
- La demanda es un supuesto simulado y la generación se fija en 0.
- No se modelan flujo AC/DC, frecuencia, protecciones, estabilidad ni energía no
  suministrada.
- Las componentes aisladas no implican falta de suministro; solo describen
  topología.
- La identidad de estaciones y la resolución de extremos son derivadas.
- El mapa muestra geometrías oficiales, pero la red agregada depende de la
  calidad de los atributos de extremos.
- El proyecto no demuestra reducción del riesgo climático ni ventaja cuántica.
- El laboratorio sintético es independiente y no representa el SEIN.

## 10. Capturas de verificación

- `docs/captures/landing-escritorio.png` — landing a 1536 px.
- `docs/captures/landing-900px.png` — mapa y hero a 900 px.
- `docs/captures/landing-390px.png` — mapa móvil con resumen colapsado.
- `docs/captures/capas-390px.png` — control de capas en móvil.

## 11. Instrucciones

Desde la raíz `D:\PROYECTOS\IBM\quantumgrid-peru`:

```powershell
# API
..\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev        # http://localhost:3001

# Activos estáticos (si cambian los datos procesados)
cd ..
..\.venv\Scripts\python.exe -m scripts.export_frontend_data

# Verificación
..\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run typecheck
npm run build
```

La app Streamlit legada sigue disponible con:

```powershell
..\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8510
```
