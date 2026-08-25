# QR Input Mesh Cleanup — Fix for xremesh 21% Stall

> Date: 2026-07-31
> Root cause: Broken input mesh (unwelded verts + open boundaries), NOT Qt/session issues.

## Problem

xremesh.exe (QuadRemesher engine) deadlocks at ~21% progress when the input FBX contains:
- **Unwelded duplicate vertices** (same position, separate vertex records)
- **Open boundary edges** (edges with only 1 linked face)

These cause xremesh's preprocessing crack-repair logic to enter pathological computation.

## Symptoms

- progress.txt stalls at ~0.21 (21%)
- No error message, process hangs indefinitely
- Same settings work fine on clean meshes

## Diagnosis

Check mesh health before QR:
```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)
nm = sum(1 for e in bm.edges if not e.is_manifold)
boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
# nm > 0 or boundary > 50 → needs cleanup
```

## Fix

Add mesh cleanup step BEFORE FBX export in QR pipeline:

```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)

# 1. Weld duplicate vertices (0.1mm threshold)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)

# 2. Fill small holes from open boundaries (cap at 30K attempts)
filled = 0
attempts = 0
for e in list(bm.edges):
    if len(e.link_faces) == 1:  # boundary edge
        attempts += 1
        if attempts > 30000:
            break
        try:
            res = bmesh.ops.edgeloop_fill(bm, edges=[e])
            filled += len(res.get("faces", []))
        except Exception:
            pass

# 3. Re-weld after fill (fill may create new duplicates)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)

bm.to_mesh(mesh.data)
bm.free()
mesh.data.update()
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Vertices | 1,137,322 | 964,764 |
| Duplicate verts | 172,559 | 0 |
| Boundary edges | 516,960 | 11 |
| QR time | stall @21% | **90 seconds** |
| Output quality | — | 253,766 faces, 100% quad, 0 non-manifold |

## Integration Point

This cleanup should run in **Step 01 (high-poly repair)** before saving the blend, not just in Step 02 (QR). This ensures the pipeline is clean from the start.

## Related

- `references/quad-remesher-headless-xremesh.md` — how to call xremesh directly
- `references/qr-semi-automatic-pattern.md` — outdated semi-auto pattern (superseded by this fix)
