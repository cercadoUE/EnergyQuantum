# Resultados sobre la subred real

Artefacto reproducible: `results/real_subnet_experiment.json`.

```powershell
..\.venv\Scripts\python.exe -m scripts.run_real_experiment
```

Configuración por defecto: subred de 6 nodos de la mayor componente verificada,
pesos por longitud, demanda uniforme abstracta (1 u.s./nodo), generación fijada
en 0, semilla 7, QAOA p=1, COBYLA, 2 048 shots, 60 iteraciones, presupuesto 400
evaluaciones / 90 s. Aer ideal en CPU.

## Subred

| Campo | Valor |
|---|---|
| Zona | Trujillo, La Libertad |
| Nodos | 6 |
| Conexiones agregadas | 6 |
| Longitud total | 51.034 km |
| Tensiones | 60, 138 y 220 kV |
| Componentes | 1 |
| Puentes | 2 |
| Ciclos (base) | 1 |

Los nodos y líneas conservan IDs y procedencia OSINERGMIN. La subred es una
muestra conectada, no el SEIN completo ni una isla eléctricamente operable.

## Solucionadores

| Método | H | Corte (pesos) | Factible | s |
|---|---:|---:|---|---:|
| Exacto | 0.2321981424 | 11.85 | Sí | ~0.003 |
| Búsqueda local | 0.2321981424 | 11.85 | Sí | ~0.019 |
| Kernighan–Lin | 0.2321981424 | 11.85 | Sí | ~0.002 |
| QAOA (6 qubits, p=1) | 0.2321981424 | 11.85 | Sí | ~0.18–0.21 |

QAOA terminó con estado `completed`, 6 qubits y una fracción factible observada
de 98.93 % en la ejecución guardada. En esta instancia pequeña los cuatro
métodos alcanzaron el mismo H. **Esto no demuestra ventaja cuántica**: la
enumeración exacta es trivial a 6 nodos y Aer es un simulador ideal.

## Falla topológica de prueba

Se retiró el puente `ed_8e3c8a73870e` (HUACA DEL SOL ↔ TRUJILLO SUR, 6.21 km).

| Indicador | Antes | Después | Δ |
|---|---:|---:|---:|
| Conexiones activas | 6 | 5 | −1 |
| Conexiones falladas | 0 | 1 | +1 |
| Componentes | 1 | 2 | +1 |
| Mayor componente | 6 | 5 | −1 |
| Nodos aislados | 0 | 1 | +1 |
| Longitud activa (km) | 51.034 | 44.824 | −6.21 |

`served_demand` y `lost_demand` son `null`. La falla es topológica: no se estima
energía no suministrada ni se modelan protecciones, flujo o re-despacho.

## Interpretación

- La topología verificada permite construir subredes conectadas y ejecutar los
  solvers existentes sin cambiar sus contratos.
- La demanda y la generación son supuestos; H no es un costo oficial ni una
  medida de riesgo.
- El corte de un puente aumenta componentes y aísla un nodo, pero eso no
  certifica un apagón.
- Los resultados son sensibles al escenario de pesos y demanda; la UI permite
  cambiar ambos y comparar por huella de instancia.
- Para el SEIN completo no se ejecuta optimización: el límite actual es 12
  nodos y la mayor componente tiene 153.
