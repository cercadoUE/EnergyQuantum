import itertools
import pytest
from src.models.graph_model import load_network, fingerprint, validate
from src.models.objective import Objective
from src.models.constraints import validate_partition
from src.algorithms.classical import brute_force, local_search, kernighan_lin
from src.simulation.failures import scenario
from src.simulation.resilience import metrics

def test_known_optimum():
    d=load_network(2); o=Objective()
    r=brute_force(d,o)
    assert r['bits']==[0,1]
    assert r['objective']==pytest.approx(1+3*(3/7)**2)
    assert r['evaluations']==1

@pytest.mark.parametrize('n',[2,4,6])
def test_qubo_and_symmetry(n):
    d=load_network(n); o=Objective(); c,l,q=o.qubo(d)
    for b in itertools.product([0,1],repeat=n):
        h=o.terms(d,b)['objective']
        assert h==pytest.approx(o.terms(d,[1-x for x in b])['objective'])
        assert h==pytest.approx(c+sum(l[i]*b[i] for i in range(n))+sum(v*b[i]*b[j] for (i,j),v in q.items()))

def test_constraints_and_methods():
    d=load_network(6); o=Objective(); ex=brute_force(d,o)
    assert not validate_partition(d,[0]*6)['feasible']
    for fn in (local_search,kernighan_lin):
        r=fn(d,o); assert r['validation']['feasible']; assert r['objective']>=ex['objective']-1e-10

def test_failure_and_hash():
    d=load_network(4); f=scenario(d,[(1,2),(0,3)])
    assert fingerprint(d)!=fingerprint(f)
    assert metrics(f)['components']==2
    assert not d['edges'][1]['failed']
    assert fingerprint(d,Objective().__dict__)!=fingerprint(d,Objective(beta=2).__dict__)

def test_invalid_input():
    d=load_network(4); d['nodes'][0]['demand']=-1
    with pytest.raises(ValueError): validate(d)
