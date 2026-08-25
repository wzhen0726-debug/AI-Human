# Retopo Mesh UV Fragmentation Fix

## Problem: 3110 UV Islands on 178K-Face Quad Remesher Output

On a 178K-face Quad Remesher character mesh, 6672 strategic seams produced **3110 UV islands** — one giant island with 175470 faces and 3089 tiny single-face islands. This causes catastrophic bake failure.

## Root Cause

The back-center + armpit + crotch seams use wide Z-band tolerance (±0.01×H), which catches almost every edge in those bands on a dense retopo mesh. Each face becomes its own island.

## Fix: Exactly 7 Seams

Reduce to exactly **7 seams** with very tight tolerance:

1. Back center line: `X=0, Y>0, tolerance=±0.005×W`
2. Left armpit: `X<0, Z≈0.76H, tolerance=±0.01×H`
3. Right armpit: `X>0, Z≈0.76H, tolerance=±0.01×H`
4. Left leg inner: `X<0, Z≈0.3H, tolerance=±0.01×H`
5. Right leg inner: `X>0, Z≈0.3H, tolerance=±0.01×H`
6. Neck ring: `Z≈0.83H, tolerance=±0.005×H`
7. Waist ring: `Z≈0.55H, tolerance=±0.005×H`

Target: <100 seams, <50 islands.

## Verification

After unwrap, run island count check:
```python
bm = bmesh.new(); bm.from_mesh(mesh)
# Flood-fill island count
islands = []; visited = set()
for f in bm.faces:
    if f.index not in visited:
        island = []; stack = [f]
        while stack:
            cf = stack.pop()
            if cf.index not in visited:
                visited.add(cf.index); island.append(cf)
                for e in cf.edges:
                    if not e.seam:
                        for lf in e.link_loops:
                            nf = lf.face
                            if nf.index not in visited:
                                stack.append(nf)
        islands.append(island)
print(f'Islands: {len(islands)}')
```

If >100 islands, the seam tolerance is too wide.