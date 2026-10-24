"""Run: python -m src.experiments.benchmark. Local budget <= 20 minutes."""
import json
import csv
import itertools
from time import perf_counter
from pathlib import Path
from ..models.graph_model import load_network, ROOT
from ..models.objective import Objective
from ..algorithms.classical import brute_force,local_search,kernighan_lin
from ..algorithms.qaoa_solver import solve
from .metrics import gap,optimal_probability,summary
from .reproducibility import environment

def main():
    start=perf_counter(); obj=Objective(); rows=[]; raw=[]; classical={}
    plan=sorted(set([(12,p,s,'COBYLA') for p in (1,2,3,4) for s in (7,11,23)]+
                    [(6,2,7,opt) for opt in ('COBYLA','SLSQP','Powell')]+
                    [(n,1,7,'COBYLA') for n in (4,6,8,10,12)]))
    out={'environment':environment(),'objective':obj.__dict__,'plan':plan,'runs':raw,'classical':classical,'rows':rows,'skipped':[],'networks':{str(n):load_network(n) for n in (4,6,8,10,12)}}
    for n in (4,6,8,10,12):
        data=load_network(n)
        classical[str(n)]=[fn(data,obj) for fn in (brute_force,local_search,kernighan_lin)]
    for n,p,seed,opt in plan:
        if perf_counter()-start>1200:
            out['skipped'].append([n,p,seed,opt]); continue
        data=load_network(n); optimum=classical[str(n)][0]['objective']
        run=solve(data,obj,p=p,maxiter=50,shots=2048,seed=seed,optimizer=opt,time_limit=45,max_evaluations=250)
        raw.append(run)
        rows.append(dict(n=n,p=p,seed=seed,optimizer=opt,optimum=optimum,best=run['objective'],expected=run.get('expected'),
                         gap=gap(run['objective'],optimum),prob_optimum=optimal_probability(run,data,obj,optimum),
                         feasible_fraction=run.get('feasible_fraction'),seconds=run['seconds'],evaluations=run['evaluations'],status=run['status']))
        print(rows[-1],flush=True)
        (ROOT/'results'/'benchmark.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    out['stability']={str(p):dict(**summary([r['best'] for r in rows if r['n']==12 and r['p']==p and r['best'] is not None]),
                             success_rate=sum(r['gap'] is not None and abs(r['gap'])<1e-7 for r in rows if r['n']==12 and r['p']==p)/3) for p in (1,2,3,4)}
    out['sensitivity']=[]
    for beta in (.1,.5,1,3,10):
        o=Objective(beta=beta); d=load_network(); r=brute_force(d,o)
        trivial=o.terms(d,[0]*12)['objective']
        out['sensitivity'].append(dict(beta=beta,feasible_optimum=r['objective'],cut=r['cut'],imbalance=r['imbalance'],trivial=trivial,trivial_beats_feasible=trivial<r['objective']))
    # Uniform random sampling baseline with the same shot budget and seeds.
    import numpy as np
    out['uniform_baseline']=[]
    d=load_network(); optimum=classical['12'][0]['objective']
    for seed in (7,11,23):
        rng=np.random.default_rng(seed); samples=rng.integers(0,2,(2048,12))
        costs=[obj.terms(d,b)['objective'] for b in samples if 0<sum(b)<12]
        out['uniform_baseline'].append(dict(seed=seed,shots=2048,best=min(costs),prob_optimum=sum(abs(c-optimum)<1e-9 for c in costs)/2048))
    out['elapsed_seconds']=perf_counter()-start
    (ROOT/'results'/'benchmark.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    with (ROOT/'results'/'benchmark.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    lines=['# Resultados ejecutados','',f"Fecha UTC: {out['environment']['timestamp_utc']}. Aer ideal; 2048 shots; 50 iteraciones máximas; presupuesto 250 evaluaciones o 45 s por ejecución.",'','| n | p | Semilla | Optimizador | H* | Mejor H | E[H] | P óptimo empírica | Factibles | s |','|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['n']} | {r['p']} | {r['seed']} | {r['optimizer']} | {r['optimum']:.5f} | {r['best']:.5f} | {r['expected']:.5f} | {r['prob_optimum']:.3%} | {r['feasible_fraction']:.3%} | {r['seconds']:.3f} |")
    lines+=['','## Estabilidad (3 semillas, desviación poblacional)','',json.dumps(out['stability'],indent=2),'','## Interpretación','El mejor de 2048 shots puede alcanzar el óptimo aunque la distribución tenga baja probabilidad óptima. La referencia uniforme con igual presupuesto permite evaluar este efecto. No se demuestra ventaja cuántica: Aer usa una computadora clásica y el exacto certifica estas instancias pequeñas. Las probabilidades son frecuencias finitas, no probabilidades exactas. Tres semillas no bastan para conclusiones generales.','', '## Sensibilidad de β','',json.dumps(out['sensitivity'],indent=2)]
    (ROOT/'docs'/'RESULTS.md').write_text('\n'.join(lines),encoding='utf8')

if __name__=='__main__': main()
