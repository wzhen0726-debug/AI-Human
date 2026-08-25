# QR Overlap Test Results (2026-07-29)

> Comprehensive test of 8+ approaches to eliminate face overlap in Quad Remesher
> output on "clothing+body" double-layer AI high-poly (Tripo, 193万面).

## Problem Statement

QR on Tripo high-poly (containing clothing + body as two surfaces) produces
~29/1000 face overlap at clothing seams (cuff, collar, waistband). Two layers
are geometrically close (0.5-5mm apart), and QR cannot distinguish them — it
creates overlapping quad faces.

## Detection Method

```python
from mathutils.bvhtree import BVHTree
import random
bvh = BVHTree.FromBMesh(bm)
random.seed(42)
sample = random.sample(list(bm.faces), min(1000, len(bm.faces)))
overlap = 0
for f in sample:
    center = f.calc_center_median()
    for d in [f.normal, -f.normal]:
        hit = bvh.ray_cast(center + d * 0.0001, d, 0.01)
        if hit[0] is not None and hit[3] != f.index:
            overlap += 1
            break
```

## Test Matrix

| # | Approach | Overlap | Non-manifold | Quad% | Notes |
|---|---------|---------|:---:|:---:|-------|
| 0 | QR 125K baseline (adaptive=50) | 29/1000 | 0 | 100% | Reference |
| 1 | QR adaptive=80 | 39/1000 | 4 | 100% | WORSE |
| 2 | QR adaptive=20, hard_edges=True | 28/1000 | 0 | 100% | Negligible |
| 3 | QR adaptive=30, hard_edges=True | 30/1000 | 0 | 100% | Negligible |
| 4 | remove_doubles(0.0001) | 29/1000 | 1 | 100% | No effect |
| 5 | Delete overlapping faces + fill_holes | 30/1000 | 1148 | 100% | Topology destroyed |
| 6 | Laplacian smooth (10 iters, factor=0.5) | 27/1000 | 0 | 100% | Negligible |
| 7 | Voxel Remesh (3mm) | 27/1000 | 0 | 100% | Lost faces (117K→96K) |
| 8 | Push verts along normal ±0.5mm | 33/1000 | 0 | 100% | WORSE |
| 9 | Decimate pre-process (body 30%, keep head/hand) | 29/1000 | 3 | 100% | No effect |
| 10 | Instant Meshes (pymeshlab) | 1/1000 | 68 | **0%** | Triangles, hand lost |
| 11 | Voxel Remesh + Quadriflow | N/A | 0 | 100% | target_faces ignored |
| 12 | Local Laplacian (overlap verts only, 20 iters) | 27/1000 | 0 | 100% | Negligible — shared neighbors move together |
| 13 | Layer-separated smooth (upper verts only, vertices_smooth ×15) | 26/1000 | 0 | 100% | Negligible |
| 14 | Push upper-layer-only verts along face normal 1mm | 35/1000 | 0 | 100% | WORSE — creates new overlaps at push boundary |
| 15 | Sculpt mode brush_stroke (SMOOTH brush) | N/A | N/A | N/A | **`brush` attribute is read-only in background mode — cannot set sculpt brush** |

## Conclusion

**QR overlap on double-layer geometry is STRUCTURAL and UNFIXABLE by post-processing.**
The only solutions are:
1. **Pre-QR**: Separate clothing from body before QR (requires AI segmentation)
2. **Accept overlap**: Bake will cover overlap regions with high-poly texture
3. **Use a different retopology tool**: Instant Meshes eliminates overlap but
   produces triangles (0% quad), loses hand detail, and introduces non-manifold edges

## Sculpt Mode Limitation (Background)

Blender's `Sculpt` mode CAN be entered in `--background` (`bpy.ops.object.mode_set(mode='SCULPT')` succeeds),
and `bpy.ops.sculpt.brush_stroke` exists as an operator. HOWEVER, `bpy.context.tool_settings.sculpt.brush`
is **read-only** — you cannot programmatically set which brush is active. A new brush can be created
(`bpy.data.brushes.new('MySmooth', mode='SCULPT')` with `brush.sculpt_brush_type = 'SMOOTH'`) but
cannot be assigned to the sculpt tool settings. This means **the Smooth sculpt brush cannot be used
in headless mode** to replicate the user's manual GUI workflow of locally smoothing overlap seams.

**Why manual sculpting works but programmatic doesn't**: The user can visually identify the exact
boundary between clothing and body layers, apply the smooth brush with a controlled radius only
to one layer's vertices, and see real-time feedback. Programmatic approaches cannot distinguish
which vertices belong to which layer (they share edges and neighbors), so all smoothing/pushing
moves both layers together.

## User Verdict

User demanded "不能重叠" (no overlap) but after exhaustive testing, this
requirement cannot be met with QR on double-layer geometry. The session ended
with this requirement UNRESOLVED.
