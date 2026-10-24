# Auditoría previa y adecuación al reto

## Materiales leídos

Bases de participación proporcionadas por el usuario (Qiskit Fall Fest 2026), imagen del reto 5.2, repositorio público y `hackathon_IBM/docs/MANUAL_EQUIPO.md`. Commit examinado: `1eedcc556be21f333b6cf2524f8e0e4e64c583c1`. Copia local de referencia fuera de la entrega principal, en `../reference`.

## Lo que existe en el repositorio

`red_electrica.py`: grafo NetworkX de 12 nodos, costo de corte más desequilibrio normalizado, SparsePauliOp ZZ, offset explícito, componentes tras corte y supuesto de impacto de falla. `clasico_red.py`: exacto, búsqueda local, KL y azar. `cuantico_red.py`: QAOAAnsatz, Aer statevector, COBYLA multirreinicio y medición final. `experimentos_red.py`: experimentos por tamaño/profundidad y exportación. `results/experimentos_red.json`: resultados guardados, no resultados reproducidos en esta auditoría. Se inspeccionaron código y artefactos; no se ejecutó su benchmark ni se certificaron sus tiempos.

## Hallazgos

1. La formulación de corte y balance y su offset son coherentes algebraicamente. No procede afirmar que toda la implementación original es ficticia.
2. Una variable binaria por nodo da dos etiquetas. La función `islas` descompone cada etiqueta en componentes: así pueden aparecer tres componentes. Es una descomposición posterior explícita, no optimización directa de tres etiquetas.
3. El impacto de falla supone pérdida de toda la red sin partición y pérdida de toda la componente con partición. Es una hipótesis de contagio, no un resultado eléctrico demostrado. No se modela generación, flujo, protecciones ni propagación física.
4. Exacto/local/QAOA pueden aceptar cadenas triviales; no hay validador independiente de restricciones operativas. KL usa otra función interna y cardinalidades equilibradas, aunque evalúa después el costo común.
5. Se ocultan warnings globalmente. No hay contrato robusto de presupuesto ni huella de escenario en los resultados examinados. Las versiones y semillas deben conservarse junto con los datos para reproducibilidad.
6. Las coordenadas son aproximadas y la red sintética. Esta entrega utiliza posiciones de diagrama, sin insinuar líneas reales.

## Decisiones de mejora

Implementación original modular, validación de entrada, separación entre objetivo/factibilidad/diagnóstico físico, contrato común de resultados, constante Ising conservada, tests exhaustivos, límites de simulación, comparación uniforme, invalidación por hash y exportación autosuficiente. No se reutilizó código del repositorio; no se observó un archivo de licencia en el inventario consultado.

## Bases y entrega

El reto solicita representar variables/costos y explorar/visualizar/comparar enfoques clásicos y cuánticos. Pitch: entre 2:30 y 3 minutos. Entregables: nombre del equipo, cuatro integrantes, enlace GitHub (Drive ZIP es opción secundaria), demo o video cuando corresponda, descripción breve y PPT, por el portal designado. Evaluación: innovación/validación 25%, Qiskit/presentación 25%, formulación del reto 20%, rigor/reproducibilidad 15%, arquitectura 15%. El guion dura aproximadamente 175 segundos y prioriza estas evidencias. No se envía al portal ni se inventan integrantes.

Las bases también piden reconocer fuentes/herramientas y evitar falsificación. Se declaran las bibliotecas, servicios y fuentes de datos usados; cualquier restricción adicional de IA anunciada por los organizadores debe ser revisada por el equipo.

## APIs verificadas

- https://qiskit.github.io/qiskit-aer/tutorials/1_aersimulator.html
- https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html
- https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.SparsePauliOp

Se usa `AerSimulator`, `save_statevector`, `transpile`, parámetros y puertas actuales de Qiskit. No se usa `execute`, Aqua ni imports heredados de Aer desde `qiskit`.
