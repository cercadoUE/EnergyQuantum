# EnergyQuantum

**Conectando decisiones inteligentes para construir redes más resilientes.**

Plataforma académica para el reto 5.2 del Qiskit Fall Fest 2026: partición binaria de una red sintética, simulación de fallas, comparación exacta/heurística/QAOA y trazabilidad experimental. Incluye además una capa de **datos reales del SEIN peruano** derivada de OSINERGMIN, separada de la red sintética y con procedencia explícita. No recomienda maniobras eléctricas.

## Ejecutar la app Streamlit

Python 3.11 recomendado. Desde esta carpeta:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8510
```

En el entorno ya preparado de esta entrega, use `..\.venv\Scripts\python.exe` en lugar de `.\.venv\Scripts\python.exe`, o ejecute `run.ps1`. Abra http://localhost:8510. La demo es local, sin credenciales IBM, cuenta en la nube ni conexión a hardware cuántico.

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m src.experiments.benchmark
```

El benchmark genera JSON completo, CSV y `docs/RESULTS.md`; sobrescribe esos tres artefactos al reproducirse. Los tiempos cambian según máquina/carga. `requirements.txt` congela las versiones instaladas de todo el entorno; `results/benchmark.json` guarda versiones, Python, sistema, semillas, parámetros, red, conteos y presupuestos.

## Plataforma web (React + MapLibre)

La entrega incluye una plataforma web nueva que conserva los solvers y la capa
real existentes. Streamlit sigue disponible como aplicación legada; el frontend
nuevo no reemplaza el código de algoritmos ni los artefactos del proyecto.

```powershell
# 1) API local (FastAPI) — desde la raíz
..\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# 2) Frontend (Vite) — en otra terminal
cd frontend
npm install
npm run dev        # http://localhost:3001

# 3) Activos estáticos del mapa (si cambian los datos procesados)
cd ..
..\.venv\Scripts\python.exe -m scripts.export_frontend_data
```

El primer acceso (`/mapa`) muestra el mapa real del Perú: fondo claro, líneas
coloreadas por tensión, líneas no verificadas discontinuas, subestaciones,
centrales y etiquetas. La barra superior indica el estado de la API y el
manifiesto; la barra inferior muestra coordenadas y zoom.

Páginas: **Mapa nacional** (`/mapa`), **Explorador de red** (`/red`),
**Subredes verificadas** (`/subredes`), **Optimización** (`/optimizacion`),
**Simulador de fallas** (`/fallas`), **Comparación** (`/comparacion`),
**Red sintética** (`/sintetico`) y **Fuentes y metodología** (`/fuentes`).

La API expone `/api/health`, `/api/network/summary`, `/api/network/components`,
`/api/network/stations`, `/api/network/edges`, `/api/subnet`, `/api/optimize`,
`/api/failure`, `/api/failure/network`, `/api/experiment`, `/api/synthetic/network`,
`/api/synthetic/optimize` y `/api/sources`. Los activos GeoJSON/JSON se generan
con `scripts/export_frontend_data.py` y se sirven desde `frontend/public/data`;
las páginas de comparación y fuentes funcionan incluso si la API no está activa.

El frontend usa TypeScript, React 19, Vite 6, MapLibre GL JS, React Router,
Recharts y Lucide. El fondo del mapa es Esri World Light Gray Base + Reference
(sin API key) y las etiquetas usan la fuente de demotiles de MapLibre. El build
se valida con `npm run typecheck` y `npm run build` dentro de `frontend`.

## Datos reales del SEIN

La red real se descarga de OSINERGMIN y se procesa en un snapshot local. La UI
no descarga datos: lee `data/processed/sein_network.json`.

```powershell
..\.venv\Scripts\python.exe -m scripts.download_sein
..\.venv\Scripts\python.exe -m scripts.build_network
..\.venv\Scripts\python.exe -m scripts.validate_network
..\.venv\Scripts\python.exe -m scripts.run_real_experiment
```

Snapshot incluido: 17 capas y 2 209 registros oficiales; 685 estaciones
procesadas, 977 líneas, 618 líneas verificadas y 501 conexiones agregadas. La
mayor componente tiene 153 nodos. COES se consultó solo como sonda de acceso:
**no hay validación COES automática** y ninguna arista se declara validada por
COES.

Cuatro pantallas adicionales:

1. **Mapa eléctrico del Perú** — subestaciones, líneas verificadas y centrales
   sobre coordenadas reales, con filtros por departamento y tensión.
2. **Explorador de subredes** — componentes, subredes conectadas de 4 a 12
   nodos, inspección de líneas y exportación.
3. **Red real · optimización** — adapta la subred a los solucionadores
   existentes, conserva IDs originales, permite pesos A–D, demanda de escenario,
   fallas y comparación antes/después.
4. **Fuentes y metodología** — manifiesto, etiquetas de procedencia, motivos de
   no verificación y limitaciones.

Etiquetas: `OFICIAL` (OSINERGMIN), `DERIVADO` (identidad, extremos, aristas,
pesos por longitud), `VALIDADO` (solo con evidencia explícita; COES no
automatizado) y `SIMULADO` (demanda, generación fijada en 0, pesos sintéticos y
fallas). Los detalles están en [fuentes](docs/DATA_SOURCES.md),
[pipeline](docs/DATA_PIPELINE.md) y
[validación topológica](docs/TOPOLOGY_VALIDATION.md).

## Recorrido de demostración

1. Inicio: observe los 12 nodos y la cota de demanda abastecible.
2. Optimización clásica: ejecute los tres métodos; examine factibilidad, corte y H.
3. Laboratorio cuántico: p=1, COBYLA, semilla 7, 2048 shots; ejecute Aer.
4. Comparación: observe brecha y frecuencia óptima; distinga H de corte bruto.
5. Quantum Explain: muestre circuito Qiskit, Hamiltoniano y conteos.
6. Simulador: retire (1,2) y (0,3); aplique. Los resultados anteriores se invalidan.
7. Vuelva a optimizar y exporte desde Resultados.
8. Mapa real: filtre por departamento/tensión y distinga conexiones verificadas.
9. Subredes reales: elija una componente, construya 6 nodos y envíela a
   «Red real · optimización».
10. Red real: ejecute clásicos/QAOA, aplique un puente como falla, compare
    antes/después y exporte. Revise «Fuentes y metodología».

## Implementación

- Doce pantallas Streamlit: ocho sintéticas y cuatro de datos reales.
- Red sintética y escenarios JSON editables, hasta 12 nodos.
- Objetivo adimensional, QUBO explícito e Ising con constante.
- Exacto elimina simetría global, búsqueda local multirreinicio y KL de NetworkX.
- QAOA parametrizado con H/RZZ/RX, optimización SciPy y simulación Qiskit Aer.
- Validadores separados: grupos no vacíos, conectividad y suficiencia agregada de generación.
- Benchmark p=1..4, tres semillas en 12 nodos, tres optimizadores en 6 nodos, tamaños 4..12, sensibilidad β y referencia uniforme.
- Pipeline real: ArcGIS REST → GeoJSON crudo → estaciones/líneas → grafo de
  extremos explícitos → subredes → instancia → solvers.
- Fallas reales sobre topología, métricas antes/después y exportaciones
  JSON/CSV/GraphML con procedencia.
- Exportaciones sintéticas JSON/CSV y presentación en `output/`.

## Documentación

- [Modelo matemático](docs/MATHEMATICAL_MODEL.md)
- [Auditoría de la referencia y bases](docs/REFERENCE_AUDIT.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Experimentos](docs/EXPERIMENTS.md) y [resultados reales](docs/RESULTS.md)
- [Fuentes de datos](docs/DATA_SOURCES.md)
- [Pipeline de datos](docs/DATA_PIPELINE.md)
- [Validación de topología](docs/TOPOLOGY_VALIDATION.md)
- [Resultados sobre la subred real](docs/REAL_DATA_RESULTS.md)
- [Limitaciones](docs/LIMITATIONS.md)
- [Pitch y respuestas técnicas](docs/PITCH.md)

## Honestidad científica

La red sintética usa localidades reales, pero enlaces, demanda, generación,
capacidad, prioridad, vulnerabilidad y posiciones son supuestos inventados. No
debe confundirse con la capa real.

La capa real usa geometrías y atributos **oficiales de OSINERGMIN**. La
identidad de estaciones, la resolución de extremos, las aristas y los pesos por
longitud son **derivados**. La demanda es un supuesto (`SIMULADO`), la
generación se fija en 0 porque no hay despacho por subestación y las fallas son
escenarios. **No hay validación COES automática**: todas las aristas tienen
`coes_validated = false`.

Una conexión verificada significa que los atributos explícitos de extremos
coinciden; no certifica suministro ni operación. No se modelan flujo AC/DC,
frecuencia, protecciones, estabilidad ni energía no suministrada. El modelo no
demuestra reducción del riesgo climático ni ventaja cuántica.

Se estudian dos etiquetas; sus componentes pueden ser más de dos. No se implementó optimización de tres grupos ni restricciones eléctricas dentro del Hamiltoniano.

