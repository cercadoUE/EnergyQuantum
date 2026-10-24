from time import perf_counter
import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import ParameterVector
from qiskit_aer import AerSimulator
from ..models.ising import to_ising, decode
from .classical import result

def circuit(data, obj, p):
    if not 1 <= p <= 4: raise ValueError('p debe estar entre 1 y 4.')
    op, offset, h, zz = to_ising(obj.qubo(data))
    scale=max([abs(float(x)) for x in h]+[abs(float(x)) for x in zz.values()]+[1e-12])
    beta=ParameterVector('beta',p); gamma=ParameterVector('gamma',p)
    qc=QuantumCircuit(len(h))
    qc.h(range(len(h)))
    for layer in range(p):
        for i,c in enumerate(h):
            if abs(c)>1e-14: qc.rz(2*gamma[layer]*float(c)/scale,i)
        for (i,j),c in zz.items():
            if abs(c)>1e-14: qc.rzz(2*gamma[layer]*float(c)/scale,i,j)
        for i in range(len(h)): qc.rx(2*beta[layer],i)
    return qc, op, offset, scale

def solve(data,obj,p=1,maxiter=60,shots=2048,seed=7,optimizer='COBYLA',time_limit=60.0,max_evaluations=500):
    start=perf_counter()
    if not 1 <= shots <= 100000 or not 1 <= maxiter <= 300 or max_evaluations < 1 or time_limit <= 0:
        raise ValueError('Budget invalide: shots 1..100000, iteraciones 1..300.')
    if optimizer not in ('COBYLA','SLSQP','Powell'): raise ValueError('Optimizador no soportado.')
    qc, op, offset, scale=circuit(data,obj,p)
    n=qc.num_qubits
    sim=AerSimulator(method='statevector',max_parallel_threads=1,max_memory_mb=512)
    compiled=transpile(qc,sim,optimization_level=0,seed_transpiler=seed)
    state=compiled.copy(); state.save_statevector()
    # Diagonal computed from the actual Pauli operator, including its identity term.
    diagonal=np.real(op.to_matrix(sparse=True).diagonal())
    scaled=(diagonal-offset)/scale
    rng=np.random.default_rng(seed); x0=rng.uniform(0,np.pi,2*p)
    trace=[]; best_x=x0.copy(); best_value=float('inf'); evals=0
    class BudgetExceeded(Exception): pass
    def expectation(x):
        nonlocal best_x,best_value,evals
        if evals>=max_evaluations or perf_counter()-start>time_limit:
            raise BudgetExceeded()
        sv=np.asarray(sim.run(state.assign_parameters(x)).result().get_statevector())
        val=float(np.abs(sv)**2 @ scaled)
        evals+=1; trace.append(val*scale+offset)
        if val<best_value: best_value,best_x=val,np.array(x).copy()
        return val
    status='completed'; converged=False; message=''
    try:
        opt=minimize(expectation,x0,method=optimizer,options={'maxiter':maxiter})
        converged=bool(opt.success); message=str(opt.message)
    except BudgetExceeded:
        status='budget_exceeded'; message='Límite de tiempo o evaluaciones alcanzado.'
    if evals==0:
        return result('QAOA',data,obj,None,start,0,seed,status=status,message=message)
    measured=compiled.assign_parameters(best_x); measured.measure_all()
    counts=sim.run(measured,shots=shots,seed_simulator=seed).result().get_counts()
    candidates=[]; feasible_shots=0; sample_expected=0.0
    for bs,count in counts.items():
        bits=decode(bs); val=obj.terms(data,bits)['objective']; sample_expected+=count*val/shots
        if 0<sum(bits)<n:
            candidates.append((val,bits)); feasible_shots+=count
    best_bits=min(candidates)[1] if candidates else None
    return result('QAOA',data,obj,best_bits,start,evals,seed,p=p,maxiter=maxiter,shots=shots,optimizer=optimizer,
                  status=status,converged=converged,message=message,expected=best_value*scale+offset,
                  sampled_expected=sample_expected,feasible_fraction=feasible_shots/shots,
                  counts=dict(counts),parameters=best_x.tolist(),parameter_order=[str(x) for x in compiled.parameters],
                  trace=trace,qubits=n,depth=compiled.depth(),gates=dict(compiled.count_ops()),
                  hamiltonian=[(label,float(c.real)) for label,c in op.to_list()],offset=offset,scale=scale,time_limit=time_limit,max_evaluations=max_evaluations)
