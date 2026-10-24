# Pipeline de datos

El pipeline es reproducible, sin GDAL/GeoPandas/Shapely/pyproj y sin descargas
desde la interfaz. La UI solo lee snapshots locales.

```text
OSINERGMIN ArcGIS REST
        │  scripts/download_sein.py
        ▼
data/raw/osinergmin/            ← GeoJSON crudo + manifest + procedencia
        │  scripts/build_network.py
        ▼
data/processed/                 ← estaciones, líneas, generación y red
        │  scripts/validate_network.py
        ▼
data/processed/sein_network.json
        │  src/ui/real_pages.py
        ▼
Streamlit: mapa, subredes, optimización real, fuentes
```

## 1. Descarga

```powershell
..\.venv\Scripts\python.exe -m scripts.download_sein
..\.venv\Scripts\python.exe -m scripts.download_sein --force --probe-coes
```

- `ArcGISClient` pagina con `resultOffset`/`resultRecordCount`, deduplica por
  `OBJECTID`, reintenta errores transitorios y cachea cada respuesta.
- `discover_targets` clasifica capas por nombre/geometría. Los IDs se leen del
  metadato vigente.
- Cada capa produce `layer_XX_<slug>.geojson`, su metadato y una entrada de
  manifiesto con `file_sha256`, conteo, páginas, campos y fecha.
- Si una capa falla y existe copia previa, se conserva la copia y se registra
  el error; no se rellenan datos faltantes.
- `--probe-coes` solo registra accesibilidad; no descarga topología.

Salida incluida: 17 capas, 2 209 registros, 0 errores.

## 2. Procesamiento

```powershell
..\.venv\Scripts\python.exe -m scripts.build_network
```

`process_snapshot` transforma los crudos sin modificarlos:

1. Normaliza Unicode/ASCII, nombres y números (`220,0` → `220.0`).
2. Descarta registros fuera del SEIN (`TIPO_SISTEMA`/`SISTEMA = "A"`) y
   geometrías inválidas.
3. Agrupa estaciones con **igual nombre normalizado y ≤ 0.75 km**. La capacidad
   resultante es el **máximo**, no la suma; se conservan todos los
   `source_ids`, capas y alias.
4. Deduplica líneas con igual código, nombre, tensión, extremos y longitud
   similar; conserva los IDs originales en `source_ids`.
5. Usa `LONGITUD` oficial si es positiva; si no, calcula la longitud geodésica
   WGS84. Una discrepancia > 2× se registra como advertencia.

Salida: `data/processed/sein_stations.json`, `sein_lines.json`,
`sein_generation.json` y `sein_processing_report.json`.

Resultado incluido: 967 estaciones crudas → 685 nodos (282 duplicados
fusionados); 986 líneas normalizadas → 977 tras deduplicar; 246 centrales.

## 3. Construcción de la topología

`build_network` crea el grafo con una regla estricta: **una línea solo se
convierte en arista si `NODO_SALIDA` y `NODO_LLEGADA` resuelven de forma
inequívoca a dos estaciones distintas**. La geometría se usa para:

- calcular longitud y dibujar la línea;
- desempatar candidatos del **mismo nombre** por cercanía al extremo;
- marcar como `far_from_geometry` un nombre que existe pero cuyo extremo está a
  más de 12 km.

Nunca se crea una conexión por cruce, cercanía o intersección de polilíneas.
Las líneas no verificadas permanecen en `network["lines"]` con su motivo, pero
no en `network["edges"]`.

Las aristas paralelas entre el mismo par se agregan en una sola arista con
`line_ids`, `line_count`, longitudes sumadas y tensiones. El grafo de
optimización conserva IDs originales y expone índices densos `0..n-1` solo al
adaptador del solver.

Salida: `data/processed/sein_network.json` y
`data/processed/sein_topology_report.json`.

## 4. Validación

```powershell
..\.venv\Scripts\python.exe -m scripts.validate_network
```

Comprueba:

- hash y conteo de cada capa cruda;
- IDs de nodo únicos, sin autoenlaces ni pares duplicados;
- todas las aristas con `validation = verified_endpoint_attributes`;
- extremos existentes, longitud positiva y `coes_validated = false`;
- reconstrucción del grafo y disponibilidad de subredes de 4 a 12 nodos.

El resultado incluido es `OK`, sin problemas.

## 5. Selección de subredes

`src/network/subnet_selector.py`:

- filtra por departamento y tensión;
- elige una componente conectada con aristas;
- crece desde la semilla de mayor grado usando las conexiones más cortas
  (heap por `length_km`);
- acepta una lista manual de nodos, pero **rechaza** selecciones no conexas;
- conserva IDs, nombres, procedencia y registros de línea;
- informa `truncated` solo cuando el crecimiento se detuvo por `max_nodes`, y
  `pool_nodes` con el tamaño de la componente disponible.

Los solucionadores actuales aceptan hasta 12 nodos. La pantalla QAOA limita a
10 qubits; el adaptador rechaza más de 12.

## 6. Instancia de optimización

`src/models/optimization_instance.py` adapta la subred al contrato existente:

- nodos con `id` denso, demanda, generación, prioridad y posición normalizada;
- aristas con costo, longitud, tensión, IDs de línea y estado;
- metadatos de escenario y `id_map` para volver a los IDs originales;
- `fingerprint()` estable (excluye la fecha de creación), usado para el
  historial de la sesión.

Modos de peso:

| Modo | Fórmula | Procedencia |
|---|---|---|
| A · longitud | `max(LONGITUD_km, 0.05)` | `DERIVADO` |
| B · normalizado | longitud / mediana | `DERIVADO` |
| C · personalizado | valor del usuario | `PERSONALIZADO` |
| D · sintético | `Uniforme(1,10)` con semilla | `SIMULADO` |

Demanda: uniforme abstracta o proxy por capacidad; ambas se etiquetan como
supuesto (`SIMULADO` / `DERIVADO`), nunca como demanda oficial. La generación
se fija en 0 porque la fuente no provee despacho por subestación.

## 7. Fallas y exportación

- `fail_edges` marca conexiones fuera de servicio en una copia; no muta la
  subred guardada.
- `subnet_metrics(include_failed=False)` calcula componentes, nodos aislados,
  puentes y longitud activa antes/después.
- `compare_metrics` reporta deltas topológicos. `served_demand` y
  `lost_demand` son `null`: no se estima energía no suministrada.
- Exportaciones: JSON completo, configuración, procedencia, nodos/aristas CSV,
  resultados CSV y GraphML. Todas conservan fuente, fecha, escenario y fallas.

## 8. Estructura de archivos

```text
scripts/download_sein.py        descarga + manifiesto + sonda COES
scripts/build_network.py        procesa + construye + guarda
scripts/validate_network.py     audita snapshot y topología
scripts/run_real_experiment.py  clásicos + QAOA + falla sobre una subred real
src/data_sources/arcgis.py      cliente REST, paginación, caché, conversión
src/data_sources/osinergmin.py  descubrimiento, descarga, snapshot, calidad
src/data_sources/coes.py        sonda de acceso, sin validación automática
src/data_sources/osm.py         extracto OSM opcional, separado
src/geospatial/geometry.py      distancias, geometría y nombres
src/geospatial/processing.py    normalización, fusión y deduplicación
src/network/graph_builder.py    resolución de extremos y grafo verificado
src/network/subnet_selector.py  componentes y subredes conectadas
src/models/optimization_instance.py  adaptador a solvers
src/simulation/real_network_failures.py  fallas y métricas reales
src/visualization/peru_map.py   mapa nacional y de subred
src/ui/real_pages.py            cuatro pantallas de datos reales
src/utils/export.py             exportaciones reales y sintéticas
```
