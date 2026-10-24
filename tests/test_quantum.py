import numpy as np
import pytest
from qiskit.quantum_info import Statevector
from src.models.graph_model import load_network
from src.models.objective import Objective
from src.models.ising import to_ising, decode
from src.algorithms.qaoa_solver import circuit, solve
from src.algorithms.classical import brute_force
from src.experiments.metrics import optimal_probability

@pytest.mark.parametrize('n',[2,4,6,12])
def test_all_ising_energies(n):
    d=load_network(n); o=Objective(); op,*_=to_ising(o.qubo(d))
    diag=op.to_matrix(sparse=True).diagonal().real
    assert op.num_qubits==n
    for i,e in enumerate(diag):
        assert e==pytest.approx(o.terms(d,decode(format(i,f'0{n}b')))['objective'],abs=1e-10)

def test_endianness_and_unitarity():
    assert decode('1001')==[1,0,0,1]
    assert decode('0010')==[0,1,0,0]
    qc,*_=circuit(load_network(4),Objective(),2)
    assert qc.num_parameters==4
    assert np.sum(Statevector.from_instruction(qc.assign_parameters([.1,.2,.3,.4])).probabilities())==pytest.approx(1)

def test_real_aer_reproducible():
    d=load_network(4); o=Objective()
    a=solve(d,o,maxiter=15,shots=256); b=solve(d,o,maxiter=15,shots=256)
    assert a['counts']==b['counts']
    assert sum(a['counts'].values())==256
    assert a['validation']['feasible']
    qc,*_=circuit(d,o,1)
    sv=Statevector.from_instruction(qc.assign_parameters(a['parameters']))
    op,*_=to_ising(o.qubo(d))
    assert float(sv.expectation_value(op).real)==pytest.approx(a['expected'])
    assert a['objective']>=brute_force(d,o)['objective']-1e-9
    assert 0<=optimal_probability(a,d,o,brute_force(d,o)['objective'])<=1

def test_budget():
    r=solve(load_network(4),Objective(),max_evaluations=2)
    assert r['status']=='budget_exceeded'
    assert r['evaluations']==2
