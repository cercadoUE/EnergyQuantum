# Arquitectura

`app.py` presenta doce secciones; `src/models` define red, objetivo, restricciones e Ising; `src/algorithms` encapsula métodos; `src/simulation` modifica copias y calcula métricas; `src/experiments` conserva protocolos y entorno; `src/visualization` genera Plotly; `src/utils` exporta contratos JSON.

La UI no calcula costos por su cuenta: utiliza el mismo modelo que las pruebas y los experimentos. La selección de nodos es por ID consecutivo, ordenado y validado. Cambios de escenario, tamaño o α/β cambian SHA-256 de datos+objetivo, vacían los resultados de sesión y previenen comparaciones obsoletas. Cambiar la semilla no invalida ejecuciones anteriores: cada resultado conserva su propia semilla.

Cada solucionador devuelve método, bits o null, tiempo medido con reloj monotónico, evaluaciones, semilla, hash de entrada, H, corte y validación. QAOA agrega configuración completa, conteos, orden y valores de parámetros, Hamiltoniano, offset, escala, trazas y terminación. Exportaciones incluyen la red completa y versiones. JSON estricto rechaza NaN.

## Capa de datos reales

La capa real es independiente de la sintética y no modifica sus contratos:

```text
ArcGIS REST (OSINERGMIN)
  → src/data_sources/arcgis.py       cliente, paginación, caché, Esri→GeoJSON
  → src/data_sources/osinergmin.py   descubrimiento, manifiesto, snapshot
  → src/geospatial/processing.py     estaciones/líneas/generación derivadas
  → src/network/graph_builder.py     aristas solo por extremos explícitos
  → src/network/subnet_selector.py   componentes y subredes conectadas
  → src/models/optimization_instance.py  adaptador a los solvers existentes
  → src/ui/real_pages.py             mapa, explorador, optimización, fuentes
```

- `scripts/download_sein.py` escribe `data/raw/osinergmin/` y un manifiesto con
  hash y fecha; nunca se ejecuta desde la UI.
- `scripts/build_network.py` escribe `data/processed/sein_network.json` y el
  reporte topológico. Los crudos no se sobrescriben.
- La regla de aristas es estricta: `NODO_SALIDA` y `NODO_LLEGADA` deben resolver
  a dos estaciones distintas. La proximidad solo desempata nombres homónimos.
- Las aristas conservan `line_ids`, procedencia y `coes_validated = false`.
- La instancia de optimización conserva IDs originales en `id_map` y entrega
  índices densos `0..n−1` a los solvers existentes.
- El historial real de la sesión se indexa por `fingerprint()` de la instancia
  (sin la fecha de creación), lo que permite comparar antes/después de una falla.
- Las cuatro pantallas reales están en `REAL_PAGES`; el resto de `PAGES` sigue
  siendo sintético. No hay un conmutador global que altere los índices de
  widgets de las pruebas existentes.

La procedencia distingue `OFICIAL`, `DERIVADO`, `VALIDADO` y `SIMULADO`. COES
solo se sondea (`NO_AUTOMATIZADA`); OSM es complementario y no se fusiona.

La sesión conserva resultados en memoria, sin cuentas ni almacenamiento remoto. Un reinicio pierde lo no exportado. El benchmark es un proceso CLI separado para evitar bloquear la interacción. No hay servicios externos ni claves en el código.

Validación: pruebas matemáticas exhaustivas, óptimo conocido, restricciones, fallas, reproducibilidad Aer, límite de evaluaciones, carga de doce páginas, ejecución/invalidation de UI, paginación/caché ArcGIS simulada, geometría, topología por extremos, subredes, instancias, fallas reales, exportaciones e integridad del snapshot. La revisión visual del navegador complementa AppTest; éste no prueba el renderizado real de Plotly.
