# Validación de topología

## Qué significa «verificado» aquí

Una conexión es **verificada** cuando la línea declara `NODO_SALIDA` y
`NODO_LLEGADA`, ambos nombres se normalizan y coinciden con estaciones
descargadas, y la resolución es inequívoca. Es una verificación de
**atributos explícitos de extremos**, no una validación eléctrica, operativa ni
de COES.

```text
línea.NODO_SALIDA ──► variantes de nombre ──► índice de estaciones
línea.NODO_LLEGADA ─► variantes de nombre ──► índice de estaciones
        │
        ├─ 0 candidatos ................ unverified_not_found
        ├─ nombre en >1 estación ....... desempate por tensión y cercanía
        │       ├─ uno a ≤12 km ........ verified
        │       ├─ todos >12 km ........ unverified_far_from_geometry
        │       └─ empate ≤0.5 km ...... unverified_ambiguous
        ├─ extremo vacío ............... unverified_missing
        ├─ misma estación .............. invalid_self_loop
        └─ geometría inválida .......... invalid_geometry
```

La cercanía **solo** desempata candidatos del mismo nombre. No se conectan
líneas por cruzarse, por terminar cerca de una estación o por intersección de
polilíneas. Las líneas no verificadas se conservan en `network["lines"]` con su
motivo y resolución, pero no generan aristas.

## Reglas de identidad y longitud

- Estaciones: mismo nombre normalizado y ≤ 0.75 km → un nodo. La capacidad es
  el máximo del grupo, no la suma. Se conservan `source_ids`, capas, alias y
  `identity_status = merged_duplicate`.
- Líneas: mismo código, nombre, tensión, extremos y longitud similar → una
  línea con varios `source_ids`.
- Aristas: pares de nodos se agregan; `length_km` es la suma de líneas
  verificadas y `line_count` indica paralelismo.
- Longitud: `LONGITUD` oficial si es positiva; si no, geodésica WGS84. Razón
  oficial/geometría fuera de `[0.5, 2.0]` se registra como advertencia.

## Resultado del snapshot incluido

Fecha de generación: `2026-10-24T18:19:27+00:00`.

| Indicador | Valor |
|---|---:|
| Estaciones procesadas | 685 |
| Estaciones en el grafo verificado | 502 |
| Estaciones aisladas | 183 |
| Líneas procesadas | 977 |
| Líneas verificadas | 618 |
| Líneas no verificadas | 359 |
| Aristas agregadas | 501 |
| Componentes del grafo | 231 |
| Componentes con aristas | 48 |
| Mayor componente | 153 nodos / 161 aristas |
| Ciclos (base) | 47 |
| Aristas validadas por COES | 0 |

### Motivos de no verificación

| Estado | Líneas | Interpretación |
|---|---:|---|
| `unverified_not_found` | 192 | El nombre del extremo no existe entre las estaciones |
| `unverified_far_from_geometry` | 143 | El nombre existe, pero el extremo está a >12 km |
| `unverified_missing` | 16 | `NODO_SALIDA` o `NODO_LLEGADA` vacío |
| `invalid_self_loop` | 5 | Ambos extremos resuelven a la misma estación |
| `unverified_ambiguous` | 3 | Varias estaciones homónimas a distancia comparable |
| **Total** | **359** | |

Estos motivos son diagnóstico, no una afirmación de que la línea no exista.
Pueden reflejar nombres históricos, variantes no cubiertas por la
normalización, geometrías simplificadas o discrepancias de la fuente.

### Controles automáticos

`data/processed/sein_topology_report.json` incluye:

```json
{
  "duplicate_node_ids": 0,
  "duplicate_edge_pairs": 0,
  "self_loops": 0,
  "invalid_geometries": 0,
  "unverified_missing_endpoints": 16,
  "coes_validated_edges": 0
}
```

`python -m scripts.validate_network` vuelve a comprobar estos controles, la
integridad de los crudos y la reconstrucción del grafo. El resultado incluido
es `OK`.

## Disponibilidad para optimización

La mayor componente verificada tiene 153 nodos, por lo que existen subredes
conectadas de 4, 6, 8, 10 y 12 nodos. La subred de ejemplo usada por la pantalla
de optimización tiene 6 nodos, 6 conexiones y 51.034 km (zona de Trujillo,
La Libertad). El tamaño no implica que la subred sea eléctricamente operable.

## Cómo reproducir la auditoría

```powershell
..\.venv\Scripts\python.exe -m scripts.validate_network
..\.venv\Scripts\python.exe -m pytest tests/test_real_data.py -q
```

Las pruebas cubren paginación/caché ArcGIS simulada, geometría, resolución de
extremos, rechazo de conexiones por cercanía, selección de subredes, instancias,
fallas, exportaciones, integridad del snapshot y el flujo de fallas en la UI.

## Advertencias

- Verificado ≠ validado por COES. `coes_validated` es `false` en todas las
  aristas.
- Una componente conectada no certifica suministro.
- No se modelan demanda, generación, flujo, frecuencia, protecciones ni
  estabilidad.
- Los 183 nodos aislados no implican falta de servicio; simplemente no tienen
  una línea verificada en este snapshot.
- Los datos de origen pueden cambiar; compare siempre con la fecha y el hash
  del manifiesto.
