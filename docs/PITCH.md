# Guion de exposición: 2:55 aproximadamente

## 1 · Problema (0:00–0:20)
En el norte peruano, una interrupción de conexiones puede aislar localidades y servicios. Para estudiar ese problema necesitamos distinguir conectividad de suministro real. EnergyQuantum es un laboratorio reproducible sobre una red sintética de doce localidades; no pretende representar líneas reales.

## 2 · Solución (0:20–0:40)
La plataforma permite inspeccionar conexiones, simular fallas y comparar particiones clásicas con QAOA. Cada resultado conserva datos, parámetros, semilla y validadores. Podemos exportarlo y reproducirlo, en lugar de presentar únicamente un gráfico atractivo.

## 3 · Modelo (0:40–1:05)
Cada nodo tiene una variable binaria. Minimizamos el costo normalizado de separar conexiones y el desequilibrio cuadrático de demanda. Exigimos dos grupos no vacíos al seleccionar candidatas. Conectividad y generación se diagnostican aparte: el Hamiltoniano no garantiza islas operables. Verificamos la equivalencia QUBO–Ising para las 4096 cadenas de doce qubits.

## 4 · Algoritmos (1:05–1:30)
El exacto certifica el óptimo. La búsqueda local y Kernighan–Lin dan referencias heurísticas, con sus diferencias documentadas. Qiskit construye el circuito de fases y mezcla; Aer calcula el estado y mide. SciPy ajusta los ángulos. Es optimización híbrida experimental, sin promesa de ventaja cuántica.

## 5 · Demo (1:30–1:55)
Mostremos el escenario, ejecutemos los métodos y observemos el corte y la validación. En Quantum Explain podemos inspeccionar el circuito y los conteos. Al retirar conexiones, la plataforma recalcula componentes y descarta resultados antiguos. Todo lo mostrado se calcula con el escenario activo.

## 6 · Evidencia (1:55–2:30)
Ejecutamos diecinueve configuraciones QAOA: profundidades uno a cuatro, tres semillas, tres optimizadores y tamaños de cuatro a doce nodos. En doce nodos las muestras incluyeron el óptimo, pero la frecuencia óptima fue baja. El mejor de muchas mediciones no implica que la distribución sea buena. Por eso mostramos esperanza, fracción factible, tiempos y una referencia uniforme con igual presupuesto. Powell llegó al límite y lo reportamos.

## 7 · Cierre (2:30–2:55)
El aporte es una cadena verificable: problema, formulación, circuito, mediciones y validación. El siguiente paso es incorporar flujo y datos validados antes de estudiar decisiones eléctricas reales. Hoy entregamos un entorno que permite aprender qué puede aportar QAOA y dónde fallan sus supuestos, con evidencia reproducible.

## Preguntas del jurado

**¿Por qué QAOA?** Es una heurística variacional adecuada para un costo binario diagonal y permite estudiar profundidad, optimización y distribuciones. No es necesario para resolver 12 nodos; se investiga su comportamiento.

**¿Qué optimiza?** Esperanza del costo de corte normalizado más desequilibrio cuadrático normalizado; no estabilidad eléctrica ni suministro efectivo.

**¿Cómo construyen Ising?** Expandimos (z_i−z_j)² y (D−2Σd_i z_i)², usamos z_i²=z_i y sustituimos z_i=(1−Z_i)/2. Conservamos offset y comprobamos todas las energías.

**¿Cómo comprueban el óptimo?** Enumeramos 2^(n−1)−1 representantes factibles aprovechando simetría de complemento; n=12 implica 2047 candidatas.

**¿Por qué puede ser más lento?** Circuitos y optimización repetida tienen overhead; simular en CPU crece exponencialmente. No se demuestra aceleración.

**¿Qué es una isla?** Aquí una componente del grafo tras retirar enlaces. Una isla eléctrica operable exige generación, regulación y condiciones físicas que este MVP no comprueba.

**¿Tres islas?** Dos etiquetas pueden contener tres componentes desconectadas. No es un modelo de tres etiquetas. Una extensión requeriría one-hot, partición jerárquica u otra codificación explícita.

**¿Qué pasa si falla un enlace?** Se retira del grafo activo, se recalculan métricas y se invalida la comparación; no se asume apagón global.

**¿Qué ejecuta Qiskit?** SparsePauliOp, circuito parametrizado, transpilación y circuito Aer para estado y mediciones. SciPy es el optimizador clásico y NetworkX evalúa grafos.

**¿Son reales los datos?** No. Los nombres son localidades, pero todos los parámetros y enlaces son supuestos sintéticos, indicados en interfaz y documentación.

**¿Qué falta para entregar al portal?** Completar nombre del equipo, cuatro integrantes y enlaces públicos accesibles. Presentar atribuciones y confirmar cualquier instrucción adicional de los organizadores.
