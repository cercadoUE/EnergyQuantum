import networkx as nx
from .graph_model import graph

def validate_partition(data, bits):
    if len(bits) != len(data['nodes']) or any(x not in (0,1) for x in bits):
        raise ValueError('Partición inválida.')
    g = graph(data)
    groups = [[i for i,b in enumerate(bits) if b == k] for k in (0,1)]
    nonempty = all(groups)
    connected = nonempty and all(nx.is_connected(g.subgraph(a)) for a in groups)
    margins = [sum(data['nodes'][i]['generation']*data['nodes'][i]['operational'] - data['nodes'][i]['demand'] for i in a) for a in groups]
    return dict(feasible=bool(nonempty), connected=bool(connected), generation_adequate=bool(nonempty and min(margins)>=0), generation_margins=margins,
                components=[sorted(c) for a in groups for c in nx.connected_components(g.subgraph(a))])
