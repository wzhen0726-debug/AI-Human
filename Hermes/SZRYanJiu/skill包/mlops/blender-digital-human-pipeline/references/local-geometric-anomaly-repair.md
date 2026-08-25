# Local Geometric Anomaly Repair — Pitfalls & Verification

> Discovered 2026-08-03 during v3_QuadRemesher 01高模修复 iteration.
> User reported symmetric double pits on chest after attempted "bump fix" — root cause was reference-plane contamination from XZ-projection overlap.

## Problem

AI-generated high-poly models (Tripo) have local geometric anomalies at clothing-body junctions (chest, belly, collar). These appear as:
- Small bumps/protrusions (positive Y displacement for -Y-facing model)
- Small dents/pits (negative Y displacement)

**Attempted fix that FAILED**: Ring-shaped reference plane push — compute a "normal surface" from a ring of neighboring vertices and push the anomaly toward it. This introduced **symmetric double pits** (two identical dents at left/right chest positions) that did not exist in the original model.

## Root Cause

The ring reference plane was computed using **XZ-plane distance** (`sqrt((x-cx)²+(z-cz)²)`), ignoring Y. Left and right chest muscles overlap in XZ projection, so the "normal surface" reference for the left chest included vertices from the right chest and vice versa. The contaminated reference pulled the true surface down to match, creating new pits.

## Correct Approach

1. **Diagnose BEFORE repairing**: Always compare against the original model first. If the anomaly exists in the original, it's an AI-generation artifact, not a repair-induced defect.
2. **Use 3D Euclidean distance** for reference plane computation: `sqrt((x-cx)²+(y-cy)²+(z-cz)²)`, never 2D projection.
3. **Small radius, multiple iterations**: Push region ≤15mm radius, strength ≤0.5, 3-5 iterations then verify before continuing.
4. **Verify against original**: After repair, sample vertices in the target region and compare to original model via KDTree nearest-neighbor. Deviation >1mm should be 0 (except in the target region).

## When to Skip Repair

If the anomaly is a **structural feature** (e.g., collar thickness, natural chest curvature), DO NOT repair — it will break the model's intended shape. Instead:
- Accept the feature as-is
- Let QR (step 02) handle it naturally (QR is robust to irregular geometry)
- Only repair if the user explicitly confirms the feature is unwanted after visual inspection

## Code Pattern (Safe Local Push)

```python
import bmesh
from mathutils import Vector, kdtree

bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()

# 3D ring reference (15mm inner, 35mm outer)
cx, cy, cz = target.x, target.y, target.z
inner_r, outer_r = 0.015, 0.035

target_verts = [v for v in bm.verts if (v.co - target).length < inner_r]
kd = kdtree.KDTree(len(bm.verts))
for vi, v in enumerate(bm.verts): kd.insert(v.co, vi)
kd.balance()

for v in target_verts:
    ring = []
    for (co, vi, dist) in kd.find_range(v.co, outer_r):
        if dist < inner_r * 0.7: continue  # exclude inner (anomaly)
        ring.append(bm.verts[vi].co)
    if len(ring) < 30: continue
    avg = Vector((0,0,0))
    for rv in ring: avg += rv
    avg /= len(ring)
    # 3D distance check — never 2D projection
    if (v.co - avg).length > 0.002:  # >2mm deviation
        v.co = v.co.lerp(avg, 0.5)  # 50% push, iterate 3-5x

bm.to_mesh(obj.data); bm.free()
```

## Verification

```python
# Compare repaired region to original
orig_kd = kdtree.KDTree(len(orig_verts))
for i, v in enumerate(orig_verts): orig_kd.insert(v, i)
orig_kd.balance()

deviated = 0
for v in repaired_verts:
    co, idx, dist = orig_kd.find(v.co)
    if dist > 0.001: deviated += 1  # >1mm
print(f"Deviated: {deviated}/{len(repaired_verts)}")  # should be ~0
```

## Files

- Working repair pipeline: `v3_QuadRemesher_交付/01高模修复与黏连检测/scripts/repair.py`
- Adhesion repair (clothing-body): `v3_QuadRemesher_交付/01高模修复与黏连检测/scripts/adhesion.py`
- Analysis doc: `v3_QuadRemesher_交付/01高模修复与黏连检测/docs/高模修复操作手册_v20.md` (难题12)
