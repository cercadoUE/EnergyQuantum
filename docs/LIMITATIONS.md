# Limitaciones

## Red sintética

- La red sintética no representa el SEIN ni líneas de transmisión reales. Todos sus valores son supuestos, sin estadísticas oficiales. La capa real se documenta por separado y no se mezcla con ella.
- Se minimiza costo de corte y desequilibrio agregado. Esto no demuestra que cortar conexiones mejore resiliencia: un corte puede empeorar la conectividad. Se muestran los indicadores antes/después para detectar ese efecto.
- No se simula clima, propagación de fallas, probabilidades de daño ni causalidad. Vulnerabilidad no es un riesgo calibrado.
- Factibilidad base significa solamente dos grupos no vacíos. Conectividad y generación son diagnósticos externos. QAOA no incorpora esas restricciones; no se reporta como solucionador de islas operables.
- La generación suficiente por etiqueta puede esconder componentes deficitarias. La cota por componente ignora capacidad, pérdidas, voltajes, frecuencia, reserva y estabilidad. Demanda efectivamente servida es null/no calculada.
- No hay flujo AC/DC ni recomendaciones de maniobras. Ninguna conclusión habilita operación de interruptores.
- Se usa Aer ideal en CPU, no hardware IBM; no hay mitigación de ruido ni demostración de ventaja cuántica. Enumeración exacta es apropiada para 12 nodos.
- KL controla cardinalidad, no demanda, y no optimiza H internamente. Sus evaluaciones externas no son comparables al conteo interno de intercambios.
- Simulación de estado y enumeración crecen exponencialmente; se limita tamaño, profundidad, evaluaciones, tiempo y memoria.
- La interfaz permite editar atributos JSON y enlaces dentro del tamaño seleccionado; añadir/quitar nodos se realiza cambiando tamaño o datos de entrada manteniendo IDs consecutivos. Tres grupos, restricciones duras de conectividad y física eléctrica son extensiones futuras.
- La aplicación es local para demo, sin persistencia multiusuario, autenticación ni despliegue público. Exportar antes de reiniciar.

## Capa real OSINERGMIN

- **Verificado no es validado.** Una arista verificada solo indica que `NODO_SALIDA` y `NODO_LLEGADA` coinciden con estaciones de la fuente. No hay validación eléctrica, operativa ni de COES.
- **COES no está automatizado.** Las páginas públicas son HTML/documentos; no se identificó un endpoint estable de nodos/aristas. `coes_validated` es `false` en todas las aristas y no se declara ninguna conexión como validada por COES.
- **Cobertura parcial.** Del snapshot incluido, 618 de 977 líneas (63 %) se verificaron. Las 359 restantes se conservan con su motivo (`not_found` 192, `far_from_geometry` 143, `missing` 16, `ambiguous` 3, `self_loop` 5) y no generan aristas. Los nombres históricos, variantes no normalizadas, geometrías simplificadas o discrepancias de la fuente pueden explicar parte de la brecha.
- **Identidad derivada.** La fusión de estaciones con igual nombre y ≤0.75 km es una decisión de identidad, no un activo oficial. La capacidad resultante es el máximo, no la suma. Los IDs de nodo (`st_*`) son derivados; los `source_ids` conservan el origen.
- **Sin demanda ni despacho.** OSINERGMIN no provee demanda por subestación en este servicio. La demanda es uniforme o un proxy de capacidad, etiquetada como supuesto. La generación se fija en 0; no se modela despacho.
- **Sin flujo ni energía no suministrada.** Las fallas son topológicas. No se calcula energía no suministrada, frecuencia, tensión, reserva, protecciones ni re-despacho. Una componente conectada no certifica suministro.
- **Subredes pequeñas.** Los solvers actuales aceptan hasta 12 nodos y la pantalla QAOA hasta 10 qubits. La mayor componente verificada tiene 153 nodos, pero la optimización se realiza sobre una muestra conectada, no sobre el SEIN completo.
- **Datos cambiantes.** El servicio puede actualizarse. El snapshot local conserva fecha, hash y manifiesto; no se afirma que sea la versión vigente. La descarga requiere red y el portal puede limitar o cambiar el servicio.
- **Geometría aproximada.** Las distancias usan WGS84 y una proyección local para punto-segmento; no sustituyen cálculos topográficos ni eléctricos. La longitud oficial se usa cuando existe; si no, es geodésica.
- **OSM no integrado.** Un extracto OSM es complementario, con licencia ODbL, y no se fusiona silenciosamente. No se usa para completar la topología oficial.
- **UI sin descarga.** Las pantallas reales leen snapshots locales; si faltan, muestran instrucciones. No hay actualización automática ni persistencia multiusuario.
