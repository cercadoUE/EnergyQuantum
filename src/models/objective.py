from dataclasses import dataclass
import numpy as np
from .graph_model import graph, validate

@dataclass(frozen=True)
class Objective:
    alpha: float = 1.0
    beta: float = 3.0

    def __post_init__(self):
        if not np.isfinite([self.alpha, self.beta]).all() or self.alpha < 0 or self.beta <= 0:
            raise ValueError('alpha >= 0 y beta > 0, finitos.')

    def terms(self, data, bits):
        z = np.asarray(bits)
        if len(z) != len(data['nodes']) or not np.isin(z, [0, 1]).all():
            raise ValueError('Partición binaria inválida.')
        d = np.array([v['demand'] for v in data['nodes']])
        g = graph(data)
        w = sum(e['cost'] for e in data['edges']) or 1.0
        cut = sum(a['weight'] for i, j, a in g.edges(data=True) if z[i] != z[j])
        delta = float(d @ (1 - 2*z))
        balance = (delta / d.sum())**2
        return dict(cut=float(cut), imbalance=delta, balance=float(balance), objective=float(self.alpha*cut/w + self.beta*balance))

    def qubo(self, data):
        validate(data)
        d = np.array([v['demand'] for v in data['nodes']], dtype=float)
        total = d.sum()
        k = self.beta/total**2
        linear = -4*k*total*d + 4*k*d*d
        pairs = {(i,j): 8*k*d[i]*d[j] for i in range(len(d)) for j in range(i+1,len(d))}
        w = sum(e['cost'] for e in data['edges']) or 1.0
        for i,j,a in graph(data).edges(data=True):
            c = self.alpha*a['weight']/w
            linear[i] += c
            linear[j] += c
            pairs[min(i,j), max(i,j)] -= 2*c
        return self.beta, linear, pairs
