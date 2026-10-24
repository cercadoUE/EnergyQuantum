# Modelo matemático

## Alcance y unidades

G=(V,E) es un grafo simple no dirigido. Las demandas d_i y generaciones g_i usan unidades sintéticas compatibles (u.s.); no son MW medidos. Los costos w_ij son unidades abstractas de separación. Capacidad y vulnerabilidad se almacenan como metadatos, no se aplican como restricciones de flujo ni probabilidades de falla. Los nodos inactivos permanecen como demanda aislada; su generación se anula y sus enlaces desaparecen.

z_i∈{0,1}. La factibilidad BASE exige 0<Σz_i<n. Los validadores de conectividad y suficiencia agregada son diagnósticos independientes, no requisitos de esa factibilidad base.

Definimos D=Σd_i>0 y W_ref=Σw_ij sobre todos los enlaces configurados, incluidos los fallados. Si todos tienen costo cero, W_ref=1. Mantener W_ref al retirar enlaces evita que una falla cambie artificialmente el peso de todos los enlaces supervivientes. Al editar costos o tamaño cambia la instancia y W_ref.

H(z)=α C_corte(z)/W_ref + β [(D−2Σd_i z_i)/D]².

C_corte usa solo enlaces activos. D_0−D_1=D−2Σd_i z_i. Ambos términos de H son adimensionales; α≥0 y β>0 son preferencias, no constantes físicas. Un corte total normalizado vale α y un desequilibrio máximo vale β. β=3 es una configuración de exploración, no una calibración empírica. Se prueba sensibilidad β∈{0.1,0.5,1,3,10}. Un aumento uniforme de todas las demandas no cambia el balance normalizado, aunque sí cambia las cotas de generación; aumentos selectivos sí modifican el problema.

## QUBO explícito

Usamos Q(z)=c+Σl_i z_i+Σ_{i<j}q_ij z_i z_j (triángulo superior, sin duplicar pares). Sea k=β/D² y a_ij=αw_ij/W_ref para enlaces activos, cero en los demás pares:

- c=β.
- l_i=−4kDd_i+4kd_i²+Σ_j a_ij.
- q_ij=8kd_id_j−2a_ij.

La identidad z_i²=z_i produce los términos lineales. `Objective.terms` calcula la definición directamente; `Objective.qubo` construye los coeficientes. Se contrastan independientemente.

## Ising y circuito

z_i=(1−Z_i)/2:

- offset=c+Σl_i/2+Σq_ij/4.
- h_i=−l_i/2−Σ_j q_ij/4 (se cancela por simetría en este modelo).
- J_ij=q_ij/4.
- H_Ising=offset I+Σh_i Z_i+ΣJ_ij Z_i Z_j.

Se conserva la identidad en SparsePauliOp y se verifica H_Ising[b,b]=H(z) para todas las cadenas de las instancias de prueba, incluida n=12. El qubit 0 es el carácter más a la derecha en etiquetas Pauli y conteos Qiskit.

El estado inicial es |+>^n. Cada capa aplica exp(−iγ(H_Ising−offset I)/s) seguida de exp(−iβ_mixΣX_i), con s=max(|h_i|,|J_ij|,10^-12). RZZ(2γJ/s), RZ(2γh/s) y RX(2β_mix) implementan las exponenciales. β_mix es un ángulo distinto del peso β de balance. Omitir offset en el circuito solo elimina una fase global. La esperanza se restaura como E[H]=s E[H_escalado]+offset. Los parámetros se guardan con el orden real de Qiskit.

## Soluciones triviales y restricciones

Ambas cadenas triviales valen β. No se añade una penalización no cuadrática oculta. Exacto y búsqueda local consideran solo grupos no vacíos; KL produce dos subconjuntos no vacíos. QAOA optimiza H sobre todo el espacio binario y aplica el filtro no vacío después de medir. Se reportan probabilidad/frecuencia factible y esperanza sin condicionar. El óptimo de referencia es el mejor H FACTIBLE. QAOA no resuelve la restricción no vacía dentro de su Hamiltoniano.

Una candidata factible con H<β certifica que el mínimo base no es trivial para esa instancia; el benchmark contrasta exactamente esta condición para cada β. No se supone que se cumple en cualquier entrada personalizada. Si la distribución no contiene candidatas factibles, se devuelve bits=null, objetivo=null y factible=false, sin fabricar solución.

La simetría H(z)=H(1−z) permite fijar z_0=0 en exacto, sin pérdida: 2^(n−1)−1 configuraciones. No aplica si se agregan restricciones asimétricas de grupo. Conectividad se calcula en el subgrafo inducido de cada grupo. Generación adecuada significa Σg_i≥Σd_i por etiqueta y no implica suficiencia por componente ni estabilidad. Las métricas poscorte sí agregan generación por componente; aun así son una cota, no suministro certificado.

## Comparabilidad

Todos reportan el mismo H original y el corte bruto por separado. KL optimiza corte sujeto a cardinalidades casi iguales, no H; se toma su mejor candidata por H entre reinicios y se documenta esa diferencia. No tiene garantía para este objetivo. Gap=100(H_alg−H*)/H* si H*>0; diferencia absoluta si H*=0. Solo se compara factibilidad base. El modelo extendido eléctrico/conexo queda fuera del MVP.
