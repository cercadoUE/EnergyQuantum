import pytest
from scripts.ibm_hardware import summarize
from src.models.graph_model import load_network
from src.models.objective import Objective
from src.algorithms.classical import brute_force

def test_counts_decode_and_feasibility():
    data=load_network(4); obj=Objective()
    exact=brute_force(data,obj)
    key=''.join(map(str,reversed(exact['bits'])))
    metrics=summarize({key:75,'0000':25},data,obj,exact['objective'])
    assert metrics['feasible_fraction']==0.75
    assert metrics['optimum_frequency']==0.75
    assert metrics['best']['bits']==exact['bits']
    assert metrics['expected']==pytest.approx(.75*exact['objective']+.25*obj.beta)

def test_invalid_measurement_width():
    with pytest.raises(ValueError):
        summarize({'00000':1},load_network(4),Objective(),0)

def test_pair_preserves_same_input_and_skips_duplicates(tmp_path, monkeypatch):
    import json
    from scripts import ibm_hardware as module
    metrics=dict(shots=1024,expected=1.,feasible_fraction=.9,optimum_frequency=.4,best={'objective':.4})
    (tmp_path/'experiment.json').write_text(json.dumps({'input_hash':'abc','aer_metrics':metrics}))
    (tmp_path/'logical.qpy').write_bytes(b'logical input')
    calls=[]
    def fake_submit(path, svc, name):
        calls.append(name)
        assert (path/'logical.qpy').read_bytes()==b'logical input'
        module.save(path/'submission.json',{'job_id':name})
    monkeypatch.setattr(module,'submit',fake_submit)
    module.run_pair(tmp_path,None,'submit-pair')
    module.run_pair(tmp_path,None,'submit-pair')
    assert sorted(calls)==sorted(module.PAIR)
    for name in module.PAIR:
        module.save(tmp_path/'comparison'/name/'hardware_result.json',dict(input_hash='abc',job_id=name,metrics=metrics))
    module.compare_pair(tmp_path)
    report=json.loads((tmp_path/'comparison'/'comparison.json').read_text())
    assert report['complete'] and len(report['rows'])==3

def test_pair_failure_preserves_other_job(tmp_path, monkeypatch):
    import json
    from scripts import ibm_hardware as module
    metrics=dict(shots=1,expected=1.,feasible_fraction=1.,optimum_frequency=1.,best={'objective':1.})
    (tmp_path/'experiment.json').write_text(json.dumps({'input_hash':'abc','aer_metrics':metrics}))
    (tmp_path/'logical.qpy').write_bytes(b'logical input')
    def fake_submit(path,svc,name):
        if name=='ibm_fez':
            raise RuntimeError('unavailable')
        module.save(path/'submission.json',{'job_id':'preserved'})
    monkeypatch.setattr(module,'submit',fake_submit)
    with pytest.raises(RuntimeError):
        module.run_pair(tmp_path,None,'submit-pair')
    assert (tmp_path/'comparison'/'ibm_kingston'/'submission.json').exists()

def test_comparison_rejects_changed_input(tmp_path):
    from scripts.ibm_hardware import pair_folders
    (tmp_path/'experiment.json').write_text('{}')
    (tmp_path/'logical.qpy').write_bytes(b'original')
    pair_folders(tmp_path)
    (tmp_path/'logical.qpy').write_bytes(b'changed')
    with pytest.raises(ValueError):
        pair_folders(tmp_path)
