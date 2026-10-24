from pathlib import Path
import json
import hashlib
import math
import networkx as nx

ROOT = Path(__file__).resolve().parents[2]

def validate(data):
    nodes, edges = data['nodes'], data['edges']
    if not 2 <= len(nodes) <= 12:
        raise ValueError('Se requieren entre 2 y 12 nodos.')
    if [v['id'] for v in nodes] != list(range(len(nodes))):
        raise ValueError('IDs deben ser consecutivos desde 0, en orden.')
    for v in nodes:
        for key in ('demand', 'generation', 'priority'):
            if not math.isfinite(v[key]) or v[key] < 0:
                raise ValueError(f'{key} debe ser finito y no negativo.')
        if len(v['position']) != 2 or not all(math.isfinite(x) for x in v['position']):
            raise ValueError('Posición visual inválida.')
        if not isinstance(v['operational'], bool):
            raise ValueError('Estado operativo debe ser booleano.')
    if sum(v['demand'] for v in nodes) <= 0:
        raise ValueError('Demanda total debe ser positiva.')
    seen = set()
    for e in edges:
        pair = tuple(sorted((e['source'], e['target'])))
        if pair in seen or pair[0] == pair[1] or any(i not in range(len(nodes)) for i in pair):
            raise ValueError('Conexión duplicada o extremos inválidos.')
        seen.add(pair)
        for key in ('cost', 'capacity', 'vulnerability'):
            if not math.isfinite(e[key]) or e[key] < 0:
                raise ValueError(f'{key} inválido.')
        if e['vulnerability'] > 1 or not isinstance(e['available'], bool) or not isinstance(e['failed'], bool):
            raise ValueError('Disponibilidad o vulnerabilidad inválida.')
    return data

def load_network(n=12):
    data = {k: json.loads((ROOT / 'data' / f'{k}.json').read_text(encoding='utf-8')) for k in ('nodes', 'edges')}
    data['nodes'] = data['nodes'][:n]
    data['edges'] = [e for e in data['edges'] if max(e['source'], e['target']) < n]
    return validate(data)

def graph(data):
    g = nx.Graph()
    for v in data['nodes']:
        g.add_node(v['id'], **v)
    for e in data['edges']:
        if e['available'] and not e['failed'] and all(data['nodes'][i]['operational'] for i in (e['source'], e['target'])):
            g.add_edge(e['source'], e['target'], weight=e['cost'])
    return g

def fingerprint(data, config=None):
    return hashlib.sha256(json.dumps([data, config], sort_keys=True, allow_nan=False).encode()).hexdigest()
