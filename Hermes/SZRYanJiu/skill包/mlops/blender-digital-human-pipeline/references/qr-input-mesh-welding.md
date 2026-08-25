# QR Input Mesh Welding — Fixing Fragmentation Before Retopology

> Discovered 2026-07-31 during v3_QuadRemesher pipeline step 02.
> Symptom: xremesh.exe stalls at ~21% progress indefinitely, regardless of session type.

## Problem

`01_highpoly_repair.blend` (Tripo T-pose, 1.93M faces) exported to `inputMesh.fbx` causes xremesh to hang at progress 0.21. The mesh looks continuous but is **topologically fragmented** — adjacent faces are not welded, creating hundreds of thousands of duplicate vertices and open boundary edges.

## Diagnosis

Run in Blender on the source mesh:

```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)

# Fragmentation signature
before = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_dist)
# weld_dist = max(0.0001, model_height * 0.00006) — ADAPTIVE, see references/adaptive-weld-overlap-detection.md
after = len(bm.verts)
print(f"Welded: {before - after}")  # >100k = fragmented

# Open boundary signature
boundary = sum(1 for e in bm.edges if e.is_boundary)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
print(f"Boundary edges: {boundary}")      # ~500k = fragmented
print(f"Non-manifold: {non_manifold}")    # often 0 (fragments are clean, just separate)
bm.free()
```

**Fragmentation signature**: `boundary_edges ≈ non_manifold_edges` and `remove_doubles` merges >100k vertices.

## Root Cause

xremesh preprocessing attempts to stitch fragmented geometry into a manifold surface. With 172k duplicate vertices and 517k boundary edges, the stitching algorithm enters a pathological state (likely O(n²) or infinite loop) and never proceeds past ~21%.

## Fix

Weld vertices + fill holes **before exporting FBX** for xremesh:

```python
import bmesh

bm = bmesh.new()
bm.from_mesh(mesh.data)

# 1. Weld duplicates
before_v = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_dist)
# weld_dist = max(0.0001, model_height * 0.00006) — ADAPTIVE, see references/adaptive-weld-overlap-detection.md
after_weld = len(bm.verts)

# 2. Fill residual holes (edgeloop_fill with attempt cap)
filled = 0
attempts = 0
for e in list(bm.edges):
    if len(e.link_faces) == 1:
        attempts += 1
        if attempts > 30000:
            break
        try:
            res = bmesh.ops.edgeloop_fill(bm, edges=[e])
            filled += len(res.get("faces", []))
        except Exception:
            pass

bm.to_mesh(mesh.data)
bm.free()
mesh.data.update()
print(f"Welded {before_v - after_weld:,} verts, filled {filled} holes")
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Vertices | 1,137,322 | 964,763 |
| Welded duplicates | — | 172,559 |
| Boundary edges | 516,960 | 11 |
| xremesh time | ∞ (stall) | **90 seconds** |
| Output quads | — | 253,766 (100% quad, 0 non-manifold) |

## Prevention

The `01_highpoly_repair` pipeline should perform the same welding **before saving the blend**, ensuring downstream steps receive manifold geometry:

```python
# In repair.py, before save:
bm = bmesh.new()
bm.from_mesh(mesh.data)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_dist)
# weld_dist = max(0.0001, model_height * 0.00006) — ADAPTIVE, see references/adaptive-weld-overlap-detection.md
# optional: fill holes, recalc normals
bm.to_mesh(mesh.data)
bm.free()
```

## Files

- Working script: `v3_QuadRemesher_交付/scripts/02_qr_auto.py` (step 2.5)
- Analysis doc: `v3_QuadRemesher_交付/02QuadRemesher拓扑/问题分析_QR全自动失败.md`
