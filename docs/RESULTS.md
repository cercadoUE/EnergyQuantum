# Resultados ejecutados

Fecha UTC: 2026-10-24T17:38:53.783305+00:00. Aer ideal; 2048 shots; 50 iteraciones máximas; presupuesto 250 evaluaciones o 45 s por ejecución.

| n | p | Semilla | Optimizador | H* | Mejor H | E[H] | P óptimo empírica | Factibles | s |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 1 | 7 | COBYLA | 0.45455 | 0.45455 | 1.01846 | 43.115% | 91.064% | 0.165 |
| 6 | 1 | 7 | COBYLA | 0.32098 | 0.32098 | 0.96530 | 2.930% | 99.658% | 0.148 |
| 6 | 2 | 7 | COBYLA | 0.32098 | 0.32098 | 0.93350 | 7.324% | 98.145% | 0.198 |
| 6 | 2 | 7 | Powell | 0.32098 | 0.32098 | 0.88596 | 1.123% | 99.854% | 0.412 |
| 6 | 2 | 7 | SLSQP | 0.32098 | 0.32098 | 0.85786 | 6.689% | 99.805% | 0.159 |
| 8 | 1 | 7 | COBYLA | 0.26637 | 0.26637 | 0.65674 | 2.393% | 99.951% | 0.222 |
| 10 | 1 | 7 | COBYLA | 0.27462 | 0.27462 | 0.77066 | 0.781% | 99.902% | 0.284 |
| 12 | 1 | 7 | COBYLA | 0.22524 | 0.22524 | 0.72698 | 0.488% | 100.000% | 0.438 |
| 12 | 1 | 11 | COBYLA | 0.22524 | 0.22524 | 0.56890 | 0.195% | 100.000% | 0.433 |
| 12 | 1 | 23 | COBYLA | 0.22524 | 0.22524 | 0.71988 | 0.439% | 100.000% | 0.458 |
| 12 | 2 | 7 | COBYLA | 0.22524 | 0.22524 | 0.66815 | 0.537% | 100.000% | 0.609 |
| 12 | 2 | 11 | COBYLA | 0.22524 | 0.22524 | 0.71891 | 0.098% | 100.000% | 0.590 |
| 12 | 2 | 23 | COBYLA | 0.22524 | 0.22524 | 0.54433 | 0.098% | 100.000% | 0.660 |
| 12 | 3 | 7 | COBYLA | 0.22524 | 0.22524 | 0.79549 | 0.049% | 100.000% | 0.750 |
| 12 | 3 | 11 | COBYLA | 0.22524 | 0.22524 | 0.51140 | 0.635% | 100.000% | 0.738 |
| 12 | 3 | 23 | COBYLA | 0.22524 | 0.22524 | 0.75434 | 0.342% | 100.000% | 0.737 |
| 12 | 4 | 7 | COBYLA | 0.22524 | 0.22524 | 0.54733 | 0.732% | 100.000% | 0.873 |
| 12 | 4 | 11 | COBYLA | 0.22524 | 0.22524 | 0.56261 | 0.439% | 100.000% | 0.875 |
| 12 | 4 | 23 | COBYLA | 0.22524 | 0.22524 | 0.80103 | 0.049% | 100.000% | 0.867 |

## Estabilidad (3 semillas, desviación poblacional)

{
  "1": {
    "mean": 0.2252446906740536,
    "std": 2.7755575615628914e-17,
    "best": 0.22524469067405356,
    "worst": 0.22524469067405356,
    "success_rate": 1.0
  },
  "2": {
    "mean": 0.2252446906740536,
    "std": 2.7755575615628914e-17,
    "best": 0.22524469067405356,
    "worst": 0.22524469067405356,
    "success_rate": 1.0
  },
  "3": {
    "mean": 0.2252446906740536,
    "std": 2.7755575615628914e-17,
    "best": 0.22524469067405356,
    "worst": 0.22524469067405356,
    "success_rate": 1.0
  },
  "4": {
    "mean": 0.2252446906740536,
    "std": 2.7755575615628914e-17,
    "best": 0.22524469067405356,
    "worst": 0.22524469067405356,
    "success_rate": 1.0
  }
}

## Interpretación
El mejor de 2048 shots puede alcanzar el óptimo aunque la distribución tenga baja probabilidad óptima. La referencia uniforme con igual presupuesto permite evaluar este efecto. No se demuestra ventaja cuántica: Aer usa una computadora clásica y el exacto certifica estas instancias pequeñas. Las probabilidades son frecuencias finitas, no probabilidades exactas. Tres semillas no bastan para conclusiones generales.

## Sensibilidad de β

[
  {
    "beta": 0.1,
    "feasible_optimum": 0.12588488765774086,
    "cut": 5.0,
    "imbalance": 29.0,
    "trivial": 0.1,
    "trivial_beats_feasible": true
  },
  {
    "beta": 0.5,
    "feasible_optimum": 0.18754078177900893,
    "cut": 9.0,
    "imbalance": -7.0,
    "trivial": 0.5,
    "trivial_beats_feasible": false
  },
  {
    "beta": 1,
    "feasible_optimum": 0.19508156355801784,
    "cut": 9.0,
    "imbalance": -7.0,
    "trivial": 1.0,
    "trivial_beats_feasible": false
  },
  {
    "beta": 3,
    "feasible_optimum": 0.22524469067405356,
    "cut": 9.0,
    "imbalance": -7.0,
    "trivial": 3.0,
    "trivial_beats_feasible": false
  },
  {
    "beta": 10,
    "feasible_optimum": 0.28307787011388125,
    "cut": 14.0,
    "imbalance": 1.0,
    "trivial": 10.0,
    "trivial_beats_feasible": false
  }
]