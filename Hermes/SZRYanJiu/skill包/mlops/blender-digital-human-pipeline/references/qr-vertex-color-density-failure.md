# QR Vertex-Color Density Control — FAILURE (2026-07-29)

## Test

Attempted to control local face density in Quad Remesher by painting vertex colors on high-poly before QR:

- Head region (Z > 0.8): red (1,0,0) = 4x density
- Hand region (|X| > 0.35, Z > 0.7): red (1,0,0) = 4x density
- Other: green (0,1,0) = 1x density

QR settings: `UseVertexColorMap=1` in RetopoSettings.txt.

## Result

QR output: **86,417 faces** — identical to the no-vertex-color run.

| Region | No vertex color | With vertex color | Change |
|--------|----------------|-------------------|--------|
| Head | 11,431 (13.2%) | 11,431 (13.2%) | 0 |
| Hand | 8,268 (9.6%) | 8,268 (9.6%) | 0 |
| Other | 66,718 (77.2%) | 66,718 (77.2%) | 0 |

**Vertex color had ZERO effect on face distribution.**

## Root Cause

Two possible causes (not isolated):

1. **xremesh.exe ignores FBX vertex color channel** — the engine may not read the `Color` layer from FBX
2. **Blender FBX exporter drops vertex colors** — `bpy.ops.export_scene.fbx(use_custom_props=False)` may not include vertex color data

Either way, **vertex-color density control is not viable** with the current QR Bridge 1.3.2 pipeline.

## Working Alternative

Increase `TargetQuadCount` + `CurvatureAdaptivness`:

| Parameter | 90K run | 150K run |
|-----------|---------|----------|
| TargetQuadCount | 90,000 | 150,000 |
| CurvatureAdaptivness | 50 | 80 |
| Total faces | 86,417 | 151,921 |
| Head faces | 11,431 (13.2%) | 20,416 (13.4%) |
| Hand faces | 8,268 (9.6%) | 15,440 (10.2%) |
| Head change | — | **+79%** |
| Hand change | — | **+87%** |
| Non-manifold edges | 0 | **6** |

Higher adaptive_size automatically allocates more faces to high-curvature regions (face, hands, joints) without any manual marking. The absolute face count increase is dramatic even though the percentage change is small.

## Warning: 150K introduces non-manifold edges

The 150K run produced **6 non-manifold edges** (vs 0 at 90K). The higher density + aggressive adaptive sizing creates tiny slivers at boundaries. Always check after QR:

```python
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
print(f"Non-manifold edges: {non_manifold}")
```

If >0, either reduce adaptive_size or run a cleanup pass.
