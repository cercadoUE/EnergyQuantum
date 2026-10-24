from time import perf_counter
import numpy as np
import networkx as nx
from ..models.constraints import validate_partition
from ..models.graph_model import graph, fingerprint

def result(method, data, obj, bits, start, evaluations, seed=None, **extra):
    return dict(method=method, bits=bits, seconds=perf_counter()-start, evaluations=evaluations, seed=seed,
                input_hash=fingerprint(data, obj.__dict__), **(obj.terms(data,bits) if bits is not None else dict(objective=None,cut=None)),
                validation=validate_partition(data,bits) if bits is not None else {'feasible':False}, **extra)

def brute_force(data, obj):
    start = perf_counter()
    n = len(data['nodes'])
    if n > 12: raise ValueError('Límite exacto: 12 nodos.')
    best, value = None, float('inf')
    for mask in range(1, 2**(n-1)):
        bits = [0]+[(mask >> i)&1 for i in range(n-1)]
        c = obj.terms(data,bits)['objective']
        if c < value: best,value = bits,c
    return result('Exacto',data,obj,best,start,2**(n-1)-1)

def local_search(data, obj, seed=7, restarts=16):
    start = perf_counter(); rng = np.random.default_rng(seed)
    n=len(data['nodes']); best=None; score=float('inf'); count=0
    if restarts < 1: raise ValueError('Se requiere al menos un reinicio.')
    for _ in range(restarts):
        bits=rng.integers(0,2,n).tolist()
        bits[0],bits[-1]=0,1
        value=obj.terms(data,bits)['objective']; count+=1
        while True:
            candidates=[]
            for i in range(n):
                b=bits.copy(); b[i]^=1
                if 0 < sum(b) < n:
                    c=obj.terms(data,b)['objective']; count+=1
                    candidates.append((c,b))
            c,b=min(candidates, default=(value,bits))
            if c >= value-1e-12: break
            value,bits=c,b
        if value<score: score,best=value,bits
    return result('Búsqueda local',data,obj,best,start,count,seed,restarts=restarts)

def kernighan_lin(data, obj, seed=7, restarts=10):
    start=perf_counter(); best=None; score=float('inf')
    if restarts < 1: raise ValueError('Se requiere al menos un reinicio.')
    for s in range(restarts):
        a,b=nx.community.kernighan_lin_bisection(graph(data),weight='weight',seed=seed+s)
        bits=[int(i in b) for i in range(len(data['nodes']))]
        value=obj.terms(data,bits)['objective']
        if value<score: best,score=bits,value
    return result('Kernighan–Lin',data,obj,best,start,restarts,seed,
                  evaluation_scope='Evaluaciones externas de H; no intercambios internos de KL',restarts=restarts)
