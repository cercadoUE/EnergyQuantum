import json
import pytest
from streamlit.testing.v1 import AppTest
from src.models.graph_model import ROOT,load_network,graph
from src.models.objective import Objective
from src.models.constraints import validate_partition
from src.algorithms.qaoa_solver import solve
from src.simulation.failures import scenario
from src.simulation.resilience import metrics
from src.utils.export import bundle

def test_export_roundtrip():
    d=load_network(4); o=Objective(); r=solve(d,o,maxiter=10,shots=128)
    exported=json.loads(bundle(d,o,{'QAOA':r}))
    assert exported['runs']['QAOA']['counts']==r['counts']
    assert exported['network']==d

def test_nonconnected_and_generation_are_diagnostics():
    d=load_network(4); v=validate_partition(d,[0,1,0,1])
    assert v['feasible'] and not v['connected'] and not v['generation_adequate']
    m=metrics(d,[0,1,0,1])
    assert m['served_demand'] is None
    assert m['potentially_supplyable'] < sum(n['demand'] for n in d['nodes'])

def test_demand_and_node_failure():
    d=load_network(4); f=scenario(d,demand_factor=2,selected_nodes=[0])
    assert f['nodes'][0]['demand']==10
    assert f['nodes'][1]['demand']==2
    f['nodes'][3]['operational']=False
    assert graph(f).degree(3)==0
    assert metrics(f)['potentially_supplyable']==0

def test_zero_cost_and_trivial_warning():
    d=load_network(4)
    for e in d['edges']: e['cost']=0
    o=Objective(); c,l,q=o.qubo(d)
    assert o.terms(d,[0,0,1,1])['objective']==pytest.approx(0)
    assert c==3

def test_ui_qaoa_export_and_failure():
    app=AppTest.from_file(ROOT/'app.py',default_timeout=30).run()
    app.sidebar.select_slider[0].set_value(4).run()
    app.sidebar.radio[0].set_value('Laboratorio cuántico').run()
    app.button[0].click().run()
    assert app.session_state['runs']['QAOA']['counts']
    for page in ['Quantum Explain','Comparación','Resultados']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
    app.sidebar.radio[0].set_value('Simulador de fallas').run()
    app.multiselect[0].set_value(['1–2','0–3'])
    app.button[0].click().run()
    assert not app.session_state['runs']
    assert metrics(app.session_state['data'])['components']==2
    assert not app.exception
