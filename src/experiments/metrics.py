import numpy as np
from ..models.ising import decode

def gap(value, optimum):
    if value is None: return None
    return 100*(value-optimum)/optimum if optimum>1e-12 else value-optimum

def optimal_probability(run,data,obj,optimum):
    if 'counts' not in run: return None
    total=sum(run['counts'].values())
    return sum(c for s,c in run['counts'].items() if 0<sum(decode(s))<len(data['nodes']) and abs(obj.terms(data,decode(s))['objective']-optimum)<1e-9)/total

def summary(values):
    return dict(mean=float(np.mean(values)),std=float(np.std(values)),best=float(min(values)),worst=float(max(values)))
