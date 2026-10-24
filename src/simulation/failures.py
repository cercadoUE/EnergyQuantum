from copy import deepcopy
from ..models.graph_model import validate

def scenario(data, failed=(), demand_factor=1.0, selected_nodes=None):
    out=deepcopy(data)
    if demand_factor < 0: raise ValueError('Factor no negativo requerido.')
    for e in out['edges']:
        if tuple(sorted((e['source'],e['target']))) in {tuple(sorted(p)) for p in failed}: e['failed']=True
    for v in out['nodes']:
        if selected_nodes is None or v['id'] in selected_nodes: v['demand']*=demand_factor
    return validate(out)
