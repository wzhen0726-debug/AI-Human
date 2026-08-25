"""Laplace flatten — STEP B (run with SYSTEM python, not Blender): sparse Laplace solve.

Usage:  python laplace_flatten_b_solve.py
Requires scipy in system python (Blender's python does NOT have scipy; an
in-Blender Jacobi fallback timed out at 600s on a 965k-vert mesh — don't do it).

Solves: y(v) = mean(y(neighbors)) for free verts, boundary verts fixed at their
current y. Free verts = inside the ellipse; everything else is the boundary ring.
The solution is the unique smooth surface that matches the chest curvature at
the ellipse boundary — no assumed plane/quadric, so it never carves natural
curvature (the failure mode of plane-fit and small-kernel median pushes).
"""
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve

NPZ_IN  = r"...\_laplace_data.npz"
NPZ_OUT = r"...\_laplace_solution.npz"

d = np.load(NPZ_IN)
V, E = d["V"], d["E"]

sol = {}
for k in range(2):
    free = d[f"free{k}"]
    nf = len(free)
    idx_map = np.full(len(V), -1, dtype=np.int64)
    idx_map[free] = np.arange(nf)
    is_free = idx_map >= 0
    Es = E[is_free[E[:,0]] | is_free[E[:,1]]]
    A = lil_matrix((nf, nf), dtype=np.float64)
    rhs = np.zeros(nf)
    deg = np.zeros(nf)
    for e in Es:
        i0, i1 = idx_map[e[0]], idx_map[e[1]]
        f0, f1 = i0 >= 0, i1 >= 0
        if f0: deg[i0] += 1
        if f1: deg[i1] += 1
        if f0 and f1:
            A[i0, i1] -= 1
            A[i1, i0] -= 1
        elif f0:
            rhs[i0] += V[e[1], 1]   # fixed neighbor contributes its y
        elif f1:
            rhs[i1] += V[e[0], 1]
    A.setdiag(deg)
    y = spsolve(A.tocsr(), rhs)
    dy = y - V[free, 1]
    print(f"bump{k}: free={nf} push min={dy.min()*1000:.2f} max={dy.max()*1000:.2f}mm")
    sol[f"free{k}"] = free
    sol[f"y{k}"] = y

np.savez_compressed(NPZ_OUT, **sol)
print("saved", NPZ_OUT)
