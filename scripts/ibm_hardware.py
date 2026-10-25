"""Prepare locally; submit explicitly; collect by ID without duplicate submission."""
import argparse
import getpass
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version
import numpy as np
from qiskit import qpy
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from src.models.graph_model import load_network, fingerprint
from src.models.objective import Objective
from src.models.ising import decode
from src.algorithms.classical import brute_force
from src.algorithms.qaoa_solver import solve, circuit

CRN = 'crn:v1:bluemix:public:quantum-computing:us-east:a/01fd5dbdd2cc469b8d1a87f81406310b:e6676ea4-d734-4d14-8090-8d0678ff5ef6::'
ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'results' / 'ibm_hardware_4q'

def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

def summarize(counts, data, obj, optimum):
    total = sum(counts.values())
    if total <= 0:
        raise ValueError('No measurements returned')
    expected = valid = optimal = 0
    best = None
    for key, count in counts.items():
        bits = decode(key)
        if len(bits) != len(data['nodes']):
            raise ValueError('Unexpected classical register size')
        cost = obj.terms(data, bits)['objective']
        expected += count * cost / total
        if 0 < sum(bits) < len(bits):
            valid += count
            if best is None or cost < best['objective']:
                best = dict(bits=bits, objective=cost)
            if np.isclose(cost, optimum, atol=1e-9, rtol=0):
                optimal += count
    return dict(shots=total, expected=expected, feasible_fraction=valid/total,
                optimum_frequency=optimal/total, best=best,
                feasibility_definition='Two nonempty groups only; no electrical feasibility')

def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'experiment.json').exists():
        raise ValueError('Preparation already exists. Use another --directory to preserve evidence.')
    data = load_network(4)
    obj = Objective()
    exact = brute_force(data, obj)
    aer = solve(data, obj, p=1, shots=1024, seed=7, maxiter=60)
    qc, _, _, _ = circuit(data, obj, 1)
    params = dict(zip(aer['parameter_order'], aer['parameters']))
    qc = qc.assign_parameters({p: params[str(p)] for p in qc.parameters})
    qc.measure_all()
    with (folder/'logical.qpy').open('wb') as f:
        qpy.dump(qc, f)
    save(folder/'experiment.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
         description='Synthetic network; simulator-trained parameters evaluated on hardware',
         data=data, objective=obj.__dict__, input_hash=fingerprint(data, obj.__dict__),
         exact=exact, aer=aer, aer_metrics=summarize(aer['counts'],data,obj,exact['objective']),
         versions={p:version(p) for p in ['qiskit','qiskit-aer','qiskit-ibm-runtime','numpy','scipy']}))
    print('Local experiment prepared:', folder)

def service(prompt):
    from qiskit_ibm_runtime import QiskitRuntimeService
    token = os.environ.get('QISKIT_IBM_TOKEN')
    if not token and prompt:
        token = getpass.getpass('IBM API key (hidden; not saved): ')
    if not token:
        raise ValueError('Missing API key. Use --prompt-token in your own terminal or set QISKIT_IBM_TOKEN.')
    return QiskitRuntimeService(channel='ibm_quantum_platform',token=token,instance=CRN)

def submit(folder, svc, backend_name=None):
    from qiskit_ibm_runtime import SamplerV2
    if (folder/'submission.json').exists() or (folder/'submit.lock').exists():
        raise ValueError('Submission already attempted. Check IBM workloads; collect existing job instead.')
    exp = json.loads((folder/'experiment.json').read_text(encoding='utf-8'))
    with (folder/'logical.qpy').open('rb') as f:
        qc = qpy.load(f)[0]
    candidates=[]
    for name in ([backend_name] if backend_name else ['ibm_fez','ibm_kingston','ibm_marrakesh']):
        try:
            backend=svc.backend(name)
            status=backend.status()
            if not status.operational or status.status_msg != 'active':
                continue
            isa=generate_preset_pass_manager(backend=backend,optimization_level=3,seed_transpiler=7).run(qc)
            two=sum(1 for inst in isa.data if len(inst.qubits)==2)
            candidates.append((status.pending_jobs,two,isa.depth(),name,backend,isa))
        except Exception as exc:
            print(name, 'unavailable:',type(exc).__name__)
    if not candidates:
        raise ValueError('No allocated operational backend found')
    selected=min(candidates,key=lambda x:x[:4])
    pending,two,depth,name,backend,isa=selected
    save(folder/'backend_selection.json',dict(criteria='pending jobs, then two-qubit gates, then depth',
         candidates=[dict(pending=x[0],two_qubit_gates=x[1],depth=x[2],backend=x[3]) for x in candidates]))
    with (folder/'isa.qpy').open('wb') as f:
        qpy.dump(isa,f)
    sampler=SamplerV2(mode=backend,options={'max_execution_time':60})
    # Keep a durable marker even if the network fails after IBM accepts the job.
    with (folder/'submit.lock').open('x', encoding='utf-8') as marker:
        marker.write(datetime.now(timezone.utc).isoformat())
    job=sampler.run([isa],shots=1024)
    save(folder/'submission.json',dict(job_id=job.job_id(),backend=name,shots=1024,
         max_execution_time=60,input_hash=exp['input_hash'],submitted_utc=datetime.now(timezone.utc).isoformat()))
    print('Submitted:',job.job_id(),'backend:',name,'Use collect; do not resubmit.')

def collect(folder, svc):
    submission=json.loads((folder/'submission.json').read_text(encoding='utf-8'))
    job=svc.job(submission['job_id'])
    status=job.status()
    print('Job status:',status)
    if status != 'DONE':
        return
    counts=job.result()[0].data.meas.get_counts()
    exp=json.loads((folder/'experiment.json').read_text(encoding='utf-8'))
    metrics=summarize(counts,exp['data'],Objective(**exp['objective']),exp['exact']['objective'])
    save(folder/'hardware_result.json',dict(**submission,counts=counts,metrics=metrics,
         runtime_metrics=job.metrics(),retrieved_utc=datetime.now(timezone.utc).isoformat()))
    print('Hardware results saved:',folder/'hardware_result.json')

PAIR = ('ibm_kingston', 'ibm_fez')

def pair_folders(folder):
    """Snapshot identical logical input without touching the original hardware run."""
    paths = {}
    for name in PAIR:
        target = folder/'comparison'/name
        target.mkdir(parents=True, exist_ok=True)
        for filename in ('experiment.json', 'logical.qpy'):
            source = folder/filename
            destination = target/filename
            if destination.exists():
                if destination.read_bytes() != source.read_bytes():
                    raise ValueError('Comparison input changed; preserve prior evidence and use another directory.')
            else:
                shutil.copyfile(source, destination)
        paths[name] = target
    return paths

def compare_pair(folder):
    exp=json.loads((folder/'experiment.json').read_text(encoding='utf-8'))
    rows=[dict(backend='Aer ideal', **exp['aer_metrics'])]
    for name in PAIR:
        path=folder/'comparison'/name/'hardware_result.json'
        if path.exists():
            result=json.loads(path.read_text(encoding='utf-8'))
            if result['input_hash'] != exp['input_hash']:
                raise ValueError('Different optimization instances cannot be compared.')
            rows.append(dict(backend=name,job_id=result['job_id'],**result['metrics']))
    output=folder/'comparison'
    output.mkdir(parents=True,exist_ok=True)
    save(output/'comparison.json',dict(complete=len(rows)==3,rows=rows,
         note='Same logical circuit and parameters; device-specific transpilation. Independent queues. One run per device is not a general ranking.'))
    lines=['# Aer vs IBM Kingston vs IBM Fez', '',
           '| Backend | Shots | E[H] | Frecuencia óptimo | Factibles | Mejor H |',
           '|---|---:|---:|---:|---:|---:|']
    for row in rows:
        best=row['best']['objective'] if row['best'] else 'Sin solución factible'
        lines.append(f"| {row['backend']} | {row['shots']} | {row['expected']:.6f} | {row['optimum_frequency']:.2%} | {row['feasible_fraction']:.2%} | {best} |")
    lines += ['', 'Factible significa dos grupos no vacíos. No certifica operación eléctrica.',
              'Mismo circuito lógico; transpilación específica para cada dispositivo. Una ejecución no demuestra superioridad general.',
              'Estado: '+('completo' if len(rows)==3 else 'pendiente de resultados hardware')]
    (output/'COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')

def run_pair(folder, svc, action):
    paths=pair_folders(folder)
    tasks={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for name,path in paths.items():
            if action=='submit-pair':
                if (path/'submission.json').exists() or (path/'submit.lock').exists():
                    print(name, 'already attempted; skipping to avoid duplicate submission')
                    continue
                tasks[pool.submit(submit,path,svc,name)]=name
            elif (path/'submission.json').exists():
                tasks[pool.submit(collect,path,svc)]=name
            else:
                print(name, 'no recorded job ID; check IBM workloads if a lock exists')
        errors=[]
        for future in as_completed(tasks):
            try:
                future.result()
            except Exception as exc:
                # Do not print remote exception bodies, which might include credentials.
                errors.append(tasks[future])
                print(tasks[future], 'failed:',type(exc).__name__, '; other job preserved')
    compare_pair(folder)
    if errors:
        raise RuntimeError('Some backends failed: '+', '.join(errors)+'. Check recorded job IDs before retrying.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','check','submit','collect','submit-pair','collect-pair','compare-pair'])
    parser.add_argument('--directory',type=Path,default=DEFAULT)
    parser.add_argument('--prompt-token',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(args.directory)
        return
    if args.action=='compare-pair':
        compare_pair(args.directory)
        return
    svc=service(args.prompt_token)
    if args.action=='check':
        print('Accessible backends:', ', '.join(b.name for b in svc.backends()))
    elif args.action=='submit':
        submit(args.directory,svc)
    elif args.action in ('submit-pair','collect-pair'):
        run_pair(args.directory,svc,args.action)
    else:
        collect(args.directory,svc)

if __name__=='__main__':
    main()
