# Fuentes de datos

Este documento separa lo que es **oficial**, lo que es **derivado**, lo que está
**validado** y lo que es **simulado**. La etiqueta de cada registro viaja con el
dato hasta la interfaz y las exportaciones.

## 1. OSINERGMIN · fuente primaria

| Campo | Valor |
|---|---|
| Institución | OSINERGMIN |
| Servicio | `https://gisem.osinergmin.gob.pe/serverosih/rest/services/Electricidad/MapaSEIN_Operacion/MapServer` |
| Tipo | ArcGIS REST `MapServer` |
| Descarga local | `data/raw/osinergmin/` |
| Fecha del snapshot incluido | `2026-10-24T18:18:45+00:00` |
| Capas descargadas | 17 |
| Registros descargados | 2 209 |
| Errores de descarga | 0 |
| Etiqueta | `OFICIAL` |

Las capas se descubren desde el metadato del servicio (`layers` y `tables`) y se
clasifican por **nombre, grupo padre y tipo de geometría**, nunca por un ID
codificado como verdad permanente. El manifiesto completo está en
`data/raw/osinergmin/manifest.json`; el historial append-only, en
`data/raw/osinergmin/procedencia.jsonl`.

### Capas utilizadas

| Rol | Capas | Registros |
|---|---|---:|
| Subestaciones (`substation`) | SET 33, 60, 138, 220 y 500 kV | 973 |
| Líneas (`line`) | L.T. 33, 60, 138, 220 y 500 kV | 989 |
| Generación (`generation`) | C.H. SEIN, C.T. SEIN, Central Reserva, Hidroeléctrica, Eólica, Solar y Biomasa | 247 |

Las capas de generación aislada (`Gen. Aislada - Municipios`, `C.H./C.T.
Aislados`) se excluyen: no pertenecen al SEIN. Los registros con
`TIPO_SISTEMA`/`SISTEMA = "A"` también se excluyen durante el procesamiento.

### Campos utilizados

- Estaciones: `OBJECTID`, `NOMBRE`, `COD_SE`, `TENSION_NOM`, `EMPRESA`,
  `DEPARTAMENTO`, `PROVINCIA`, `DISTRITO`, `CAPACIDAD`, `TRANSFORMADORES`,
  `ESTADO`, `TIPO_SISTEMA`, `REGION_GEOGRAFICA`.
- Líneas: `OBJECTID`, `COD_LINEA`, `NOMBRE`, `TENSION_NOM`, `LONGITUD`,
  `NODO_SALIDA`, `NODO_LLEGADA`, `ESTADO`, `EMPRESA`, `AREA_SEIN`, `SISTEMA`,
  `TIPO_CIRCUITO`, `MAT_CODUC`.
- Generación: `OBJECTID`, `NOMBRE`, `TIPO_CENTRAL`, `TENSION_NOM`, `POT_INST`,
  `POT_EFEC`, `EMPRESA`, `DEPARTAMENTO`, `ESTADO`, `FUENTE_ENER`.

La descarga usa `outSR=4326` y `f=geojson`; si el servicio no devuelve GeoJSON,
el cliente convierte geometrías Esri JSON (`point`, `paths`, `rings`). No se
usan coordenadas sintéticas para los datos reales.

## 2. COES · sonda de acceso, no validación

Se consultaron dos páginas públicas:

| Recurso | HTTP | Accesible | Topología máquina-máquina |
|---|---:|---|---|
| Diagrama unifilar | 200 | Sí | No |
| Base de datos | 200 | Sí | No |

Resultado registrado en `data/raw/coes/probe.json`:
`validation_status = NO_AUTOMATIZADA`.

El diagrama unifilar es un documento gráfico y las páginas no exponen un
endpoint estable de nodos/aristas. Por eso **ninguna conexión se declara
validada por COES** y `coes_validated` es `false` en todas las aristas. La
contrastación documental manual queda fuera de esta versión.

## 3. OpenStreetMap · fuente complementaria opcional

`src/data_sources/osm.py` puede convertir un extracto `.osm` local
(Geofabrik/Overpass) en GeoJSON de elementos `power=line`, `minor_line`,
`cable`, `substation`, `plant`, `generator` y `transformer`. Se etiqueta como
`COMPLEMENTARIO` y **nunca se fusiona en silencio** con OSINERGMIN. No se
descarga el PBF nacional automáticamente.

## 4. Etiquetas de procedencia

| Etiqueta | Significado | Ejemplos |
|---|---|---|
| `OFICIAL` | Descargado de la fuente, sin reinterpretar | geometrías y atributos OSINERGMIN, generación |
| `DERIVADO` | Transformación reproducible de datos oficiales | identidad de estaciones, extremos resueltos, aristas, longitudes, pesos por longitud |
| `VALIDADO` | Existe evidencia explícita documentada | reservado; COES no está automatizado |
| `SIMULADO` | Supuesto de escenario, no dato de la fuente | demanda uniforme, generación fijada en 0, pesos sintéticos, fallas |

La UI muestra estas etiquetas en «Fuentes y metodología» y en cada exportación.
Un resultado calculado por QuantumGrid **no** es un dato oficial.

## 5. Reproducibilidad y caché

- Cada respuesta ArcGIS se cachea en `data/cache/arcgis/` con URL, parámetros,
  fecha y hash. Sin red, se reutiliza la última copia y se advierte.
- El archivo crudo es inmutable: el procesamiento escribe solo en
  `data/processed/`.
- `scripts/validate_network.py` verifica hash, conteos, geometrías y topología
  sin tocar la red.
- Los datos de OSINERGMIN pueden cambiar; el snapshot local conserva la fecha y
  el hash de lo descargado. No se afirma que el servicio sea estático.

## 6. Licencias y atribución

Los datos se obtienen de portales públicos de OSINERGMIN y COES. Se citan la
institución, el servicio, la fecha y el hash; no se reclama propiedad sobre
ellos. OpenStreetMap, si se usa, conserva su licencia ODbL-1.0. Las bibliotecas
de software conservan sus licencias respectivas.
