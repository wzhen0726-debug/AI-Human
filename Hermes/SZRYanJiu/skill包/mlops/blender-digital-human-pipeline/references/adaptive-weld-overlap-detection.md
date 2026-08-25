# Adaptive remove_doubles Threshold + Overlap Detection

> Verified 2026-07-31 on Blender 5.1. Tripo T-pose model resized from 0.98m to 1.81m height.

## Problem 1: Fixed remove_doubles threshold fails on resized models

The original repair pipeline used a fixed `remove_doubles(threshold=0.00005)` (0.05mm). This worked for a ~1m model but when the user resized to 1.81m, the same threshold was proportionally too small — 172K duplicate vertices remained unwelded, causing QR's xremesh to stall at 21%.

### Fix: Adaptive threshold based on model height

```python
mn, mx, dims = get_bbox(obj)
model_height = dims[2]
adaptive_threshold = max(0.0001, model_height * 0.00006)  # ~0.1mm per 1.7m
```

**Formula rationale**: At 1.7m height → 0.000102m (0.102mm). At 1.81m → 0.000109m (0.109mm). The floor of 0.0001 (0.1mm) prevents over-merging on tiny models.

**Tuning history**:
- `0.00005` (0.05mm) — original, too small for 1.81m model (172K verts unwelded)
- `0.0002` (0.2mm) — too large, caused 59 non-manifold edges + 31 boundary edges on same model
- `0.0001` (0.1mm) with `× 0.00006` scaling — **correct**: 2 non-manifold edges, 0 boundary, PASS

**Apply to BOTH repair steps**: The same adaptive threshold must be used in:
1. Step [3] initial `remove_doubles`
2. Step [8] final `remove_doubles` (use the same `adaptive_threshold` variable)
3. `final_weld_for_qr()` — must compute its own `weld_dist = max(0.0001, model_height * 0.00006)`
4. `02_qr_auto.py` step 2.5 — must also compute adaptively (not hardcoded 0.0001)

## Problem 2: Overlapping faces at chest / clothing-body junction

AI high-poly meshes (Tripo) often have **coincident duplicate faces** — two faces at the exact same position with the same normal. These are different from clothing-body parallel layers (which have opposite normals and should NOT be removed).

### Fix: BVH ray-cast overlap detection

```python
from mathutils.bvhtree import BVHTree

bvh = BVHTree.FromBMesh(bm)

for i in range(scan_limit):  # max 500K faces, 120s timeout
    f = bm.faces[i]
    center = f.calc_center_median()
    normal = f.normal.normalized()
    
    # Ray from face center along normal, 2mm range
    hit = bvh.ray_cast(center + normal * 0.0001, normal, 0.002)
    
    if hit[0] is not None and hit[2] is not None:
        hit_face = bm.faces[hit[2]]
        dot = normal.dot(hit_face.normal.normalized())
        
        if dot > 0.95:  # SAME normal direction = true duplicate
            # Remove the smaller face
            if f.calc_area() < hit_face.calc_area():
                faces_to_remove.add(f.index)
            else:
                faces_to_remove.add(hit_face.index)
        
        # dot < -0.95 (opposite normals = clothing-body layer) → DO NOT REMOVE
        # Removing these creates holes
```

**Critical**: Only remove faces with `dot > 0.95` (same normal). Faces with `dot < -0.95` (opposite normals) are clothing-body parallel layers — removing either side creates a visible hole.

**Performance**: BVH tree makes this near-linear. 500K faces scanned in ~2 seconds. The 120s timeout and 500K scan limit are safety caps.

**Result**: On Tripo 1.93M-face model, detected 1 true duplicate face (dot > 0.95). The "overlapping" the user sees at the chest is primarily **parallel-layer clothing-body geometry** (dot < -0.95), which is the AI model's inherent structure and cannot be auto-removed without creating holes. Manual GUI sculpting with a radius-limited smooth brush is the only known fix for parallel-layer overlap (confirmed 2026-07-29).

## Pipeline integration

The `remove_overlapping_faces()` function is called as **step [6.5]** in `repair_pipeline()`, between `fix_non_manifold_edges` (step 6) and `laplacian_smooth` (step 7):

```
[6]   Fix non-manifold edges
[6.5] Remove overlapping faces (BVH ray-cast, same-normal only)
[7]   Laplacian smooth
[8]   Final remove_doubles (adaptive threshold) + fill holes
```
