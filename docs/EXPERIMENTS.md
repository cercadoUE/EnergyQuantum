# Protocolo experimental

Ejecute `python -m src.experiments.benchmark` desde la raíz del proyecto. El protocolo usa α=1, β=3, 2048 shots, 50 iteraciones máximas, límite de 250 evaluaciones y 45 s de optimización por ejecución; Aer usa un hilo y máximo 512 MiB. Hay un límite global de 1200 s. Una evaluación en curso y medición/postprocesado pueden superar ligeramente el límite temporal; no es un temporizador de cancelación dura. El MVP limita n≤12 y p≤4. El estado de 12 qubits tiene 4096 amplitudes complejas (64 KiB en complex128, sin contar overhead).

1. Profundidad: n=12, p=1,2,3,4 y semillas 7,11,23.
2. Optimizadores: n=6,p=2, semilla 7; COBYLA, SLSQP y Powell. El número de iteraciones no equivale a evaluaciones entre métodos, por ello existe tope común de evaluaciones.
3. Estabilidad: media/desviación poblacional/mejor/peor del mejor H medido y tasa de alcanzar H* por profundidad (3 semillas). No es una estimación estadística robusta de desempeño general.
4. Escalabilidad: n=4,6,8,10,12, p=1, semilla 7, COBYLA; subgrafos inducidos sobre primeros n nodos, renormalización explícita de D y W_ref.
5. Sensibilidad: exacto para β=0.1,0.5,1,3,10; comparación con cadena trivial de energía β.
6. Referencia aleatoria: 2048 cadenas uniformes para cada semilla en n=12. La selección del mejor entre muchas muestras puede explicar éxito aparente aun con baja probabilidad óptima.

19 configuraciones QAOA únicas (la de n=12,p=1,semilla 7 se comparte entre profundidad y escalabilidad). Se registran todas las candidatas medidas, no solo las favorables. `completed` indica que SciPy devolvió control; consulte `converged` y `message` para saber si alcanzó convergencia o solo el máximo de iteraciones. `budget_exceeded` indica interrupción por presupuesto conservando el mejor estado evaluado.

La esperanza es exacta bajo vector de estado ideal y se calcula sobre toda la distribución. La probabilidad óptima y fracción factible son frecuencias de las mediciones finales. La mejor solución es la de menor H entre muestras factibles. No debe confundirse con la cadena más probable. La medición final se realiza con Aer, no se sustituye por el óptimo clásico.

Los resultados se encuentran en `RESULTS.md` y `results/benchmark.json`. Reproducir con versiones fijas y misma semilla suele reproducir conteos; otras plataformas/BLAS/versiones pueden cambiar trayectorias numéricas. Los tiempos no son portables. Para publicar conclusiones se requieren más semillas, presupuestos equiparables, intervalos de confianza, instancias diversas y modelos de ruido/hardware.
