import numpy as np
from qiskit.quantum_info import SparsePauliOp

def to_ising(qubo):
    constant, linear, pairs = qubo
    n = len(linear)
    h = -np.array(linear)/2
    offset = constant + sum(linear)/2
    zz = {}
    for (i,j), q in pairs.items():
        offset += q/4
        h[i] -= q/4
        h[j] -= q/4
        zz[i,j] = q/4
    terms = [('I'*n, float(offset))]
    for indices,c in [*(( (i,),c) for i,c in enumerate(h)), *((ij,c) for ij,c in zz.items())]:
        if abs(c) > 1e-14:
            label = ['I']*n
            for i in indices: label[n-1-i] = 'Z'
            terms.append((''.join(label),float(c)))
    return SparsePauliOp.from_list(terms), float(offset), h, zz

def decode(bitstring):
    return [int(b) for b in bitstring.replace(' ', '')[::-1]]
