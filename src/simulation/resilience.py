import networkx as nx
from ..models.graph_model import graph

def metrics(data, bits=None):
    g=graph(data)
    if bits is not None:
        g.remove_edges_from([(i,j) for i,j in g.edges if bits[i]!=bits[j]])
    components=list(nx.connected_components(g)); unreachable=[]; potential=0
    for c in components:
        d=sum(data['nodes'][i]['demand'] for i in c)
        gen=sum(data['nodes'][i]['generation']*data['nodes'][i]['operational'] for i in c)
        if gen<=0: unreachable.extend(c)
        potential+=min(d,gen)
    return dict(components=len(components),largest_component=max(map(len,components)),
                disconnected_nodes=sorted(unreachable),disconnected_demand=sum(data['nodes'][i]['demand'] for i in unreachable),
                potentially_supplyable=potential,served_demand=None,
                affected_edges=len(data['edges'])-graph(data).number_of_edges(),bridges=[list(e) for e in nx.bridges(g)])
