# Repair Pipeline v6 — High-Poly Geometry Repair (2026-07-23)

Complete overhaul of `repair.py` for the Quad Remesher Simplified Pipeline
(sub-workflow D). Turns raw AI GLB (1-2M faces, open shell, non-manifold)
into a watertight manifold proxy (~34K faces) ready for QR retopology.

## Raw Model Characteristics (Tripo AI)

- 1,137,322 vertices / 1,930,148 faces / 3,153,702 edges
- 516,960 non-manifold edges (16.4% — open shell, NOT watertight)
- Dimensions: X=0.17m (body depth), Y=0.98m (arm span), Z=0.976m (height)
- Orientation: arms along Y, face toward +X (Tripo default)

## Pipeline Steps (11 stages)

1. **Orientation detection & rotation**: Detect `dim_y > dim_x * 1.8` →
   rotate 90° CW around Z: `new_x = old_y, new_y = -old_x`. Result: arms
   along X, face toward -Y, Z up.
2. **Center & ground**: Subtract centroid X/Y, subtract min Z. Model
   centered at origin with feet at Z=0.
3. **Pre-voxel cleanup**: `bmesh.ops.dissolve_faces()` for zero-area
   faces, remove loose verts. Count non-manifold edges (informational —
   Voxel Remesh will fix them).
4. **Remove doubles**: `bpy.ops.mesh.remove_doubles(threshold=0.0001)`.
   On the Tripo model: 1.13M → 964K verts (merges 173K duplicates).
5. **Fill holes**: `bpy.ops.mesh.fill_holes(sides=0)` — fill all boundary
   edge loops.
6. **Voxel Remesh**: Adaptive `voxel_size = height / 195.0`, clamped to
   [0.003, 0.008]. For 0.976m → 0.005, producing ~34K faces. Uses
   `use_remove_disconnected=True` and `use_smooth_shade=True`.
7. **Post-voxel cleanup**: Dissolve degenerate faces again (voxel can
   create 1-2 zero-area faces).
8. **Recalculate normals**: `normals_make_consistent(inside=False)` —
   ensure all normals face outward.
9. **Laplacian smooth**: 3 iterations, factor=0.3. Uses
   `vertices_smooth_laplacian` (volume-preserving) with fallback to
   `vertices_smooth`.
10. **Final fill + remove doubles + re-ground**: `fill_holes(sides=0)` →
    `remove_doubles(threshold=0.0001)` → `fill_holes(sides=0)` →
    `normals_make_consistent(inside=False)`. Then re-ground: subtract
    `min(Z)` from all verts (smoothing shifted Z by ~2mm).
11. **Quality verification**: 11 checks (see below).

## Key Technique: Degenerate Face Cleanup

**Problem**: Voxel Remesh produces 1-2 zero-area faces. Removing them
with `bm.faces.remove()` creates holes (boundary edges), breaking
watertightness. Dissolving with `bmesh.ops.dissolve_faces()` merges into
neighbors but can leave a residual degenerate face.

**Solution**: The `remove_doubles` + `fill_holes` combo after dissolve:
```python
bpy.ops.mesh.remove_doubles(threshold=0.0001)  # merge coincident verts
bpy.ops.mesh.fill_holes(sides=0)                # close any holes
bpy.ops.mesh.normals_make_consistent(inside=False)
```
`remove_doubles` merges vertices that are <0.1mm apart, which eliminates
the zero-area faces by merging their coincident vertices into one. Then
`fill_holes` closes any gaps this might create.

## Key Technique: Adaptive Voxel Size

```python
def calc_adaptive_voxel_size(obj, target_faces=40000):
    mn, mx, dims = get_bbox(obj)
    height = dims[2]
    voxel_size = height / 195.0
    return max(0.003, min(0.008, voxel_size))
```

Empirical: `height / 195` produces ~34K faces for a 1m-tall humanoid.
This scales proportionally — a 1.5m model gets voxel_size=0.0077
(coarser, fewer faces), a 0.6m model gets 0.003 (finer, more faces).

## Quality Check Script (`repair_qa.py`)

11 checks, all must pass:

| Check | Condition | Why |
|-------|-----------|-----|
| non_manifold_edges | == 0 | QR requires manifold input |
| boundary_edges | == 0 | Watertight = no open edges |
| loose_verts | == 0 | No floating vertices |
| degenerate_faces | == 0 | No zero-area faces |
| watertight | True | Boundary == 0 |
| manifold | True | Non-manifold == 0 |
| oriented_arms_along_x | dim_x > dim_y * 1.5 | Arms along X |
| centered_x | |cx| < 0.001 | Centered on origin |
| centered_y | |cy| < 0.001 | Centered on origin |
| grounded_z | |min_z| < 0.001 | Feet at Z=0 |
| face_count_range | 20K ≤ faces ≤ 60K | Proxy density |
| height_range | 0.8m ≤ dim_z ≤ 2.5m | Plausible humanoid |

Run: `blender --background 01_repair.blend --factory-startup --python repair_qa.py`

## Verified Results (2026-07-23)

- Input: 1,137,322 verts / 1,930,148 faces / 516,960 non-manifold edges
- Output: 34,378 verts / 34,398 faces
- Watertight: True | Manifold: True | Degenerate: 0 | Boundary: 0
- Oriented: arms along X (0.976m) | Centered: X=0, Y=0 | Grounded: Z=0
- All 11 QA checks: PASS
- Vision verification (front + side renders): recognizable humanoid,
  T-pose, no holes, surface smooth for QR

## Pipeline Script Location

`test03_SimplifiedPipeline/scripts/repair.py` (383 lines)
`test03_SimplifiedPipeline/scripts/repair_qa.py` (94 lines)
`test03_SimplifiedPipeline/scripts/render_repair_check.py` (render for vision QA)

Config: `voxel_size=0.0` (adaptive), `smooth_iterations=3`, `smooth_factor=0.3`
