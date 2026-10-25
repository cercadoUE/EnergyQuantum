# Prueba IBM Quantum

## Comparar Kingston y Fez

Desde PowerShell en la raíz, introducir la clave oculta una sola vez por comando:

```powershell
..\.venv\Scripts\python.exe -m scripts.ibm_hardware submit-pair --prompt-token
..\.venv\Scripts\python.exe -m scripts.ibm_hardware collect-pair --prompt-token
```

submit-pair envía dos trabajos nuevos concurrentemente, uno por dispositivo,
con el mismo circuito lógico, parámetros y 1024 shots. Cada trabajo tiene límite
de ejecución de 60 s (hasta 120 s entre ambos; no es tiempo de cola ni duración
garantizada). IBM agenda cada dispositivo independientemente. No reutiliza ni
sobrescribe la ejecución original de Kingston. No reentrena parámetros.
Los circuitos físicos pueden diferir debido a la transpilación.

Repetir collect-pair hasta que ambos terminen. Los IDs y circuitos se conservan
por dispositivo en results/ibm_hardware_4q/comparison/. comparison.json y
COMPARISON.md contienen Aer y los resultados hardware disponibles, marcando
si faltan resultados. No se inventan valores pendientes. Un fallo en un envío
no borra el otro; los marcadores evitan duplicados. Una sola ejecución por QPU
no permite afirmar que un procesador sea generalmente superior al otro.

Preparación local: `python -m scripts.ibm_hardware prepare` (ya ejecutada).
Instalar integración opcional: `pip install -r requirements-ibm.txt`.

Desde la raíz del proyecto, en una terminal personal:

```powershell
..\.venv\Scripts\python.exe -m scripts.ibm_hardware check --prompt-token
..\.venv\Scripts\python.exe -m scripts.ibm_hardware submit --prompt-token
..\.venv\Scripts\python.exe -m scripts.ibm_hardware collect --prompt-token
```

La entrada de API key está oculta y no se guarda. También se admite la variable
de entorno QISKIT_IBM_TOKEN. No publicar claves. El CRN de la instancia Test está
configurado en el script; no es una credencial de autenticación.

`check` consulta acceso; `submit` consume cuota: un circuito sintético de 4 qubits,
p=1, 1024 shots, parámetros entrenados en Aer, límite de ejecución de 60 segundos.
Se selecciona un backend operativo asignado entre fez, kingston y marrakesh por
cola, compuertas de dos qubits y profundidad. No garantiza mejor fidelidad.
No usa sesiones. La espera en cola es independiente del límite de ejecución.

`collect` consulta una vez el estado y descarga resultados solo cuando termina.
Repetir collect no envía nuevos trabajos. Si submit falla tras crear submit.lock,
comprobar primero Workloads en IBM para evitar duplicados. No borrar el marcador
y reenviar a ciegas. El ID se conserva en submission.json cuando se recibe.

Evidencia en results/ibm_hardware_4q: red, objetivo, óptimo exacto, parámetros,
versiones, conteos Aer, circuitos QPY y, después de ejecutar, selección de backend,
Job ID y métricas hardware. La factibilidad solo exige dos grupos no vacíos.
Esto es evaluación en hardware de parámetros entrenados en simulación, no
optimización variacional completa en hardware ni prueba de ventaja cuántica.
