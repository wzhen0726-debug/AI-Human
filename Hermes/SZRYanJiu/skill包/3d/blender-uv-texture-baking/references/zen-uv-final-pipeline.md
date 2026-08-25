# ZEN UV Final Pipeline — Best Configuration for QR Meshes

## Critical Discovery: `zenuv_unwrap_inplace(CONFORMAL)` works in background (2026-07-21)

While `zenuv_unwrap()` crashes (`EXCEPTION_ACCESS_VIOLATION`),
**`zenuv_unwrap_inplace(urp_method='CONFORMAL')` works stably** in `--background`.
This applies LSCM unwrap to existing UV islands — much better than ANGLE_BASED:
```python
bpy.ops.uv.zenuv_unwrap_inplace(urp_method='CONFORMAL', fill_holes=True,
    correct_aspect=True, restore_location=True, restore_size=True)
```
But `zenuv_relax` crashes on zero-length vectors (`RuntimeError: Vector.angle(other):
zero length vectors have no valid angle`) — skip it.

## Best Pipeline (auto_uv_unwrap + CONFORMAL inplace, 2026-07-21)

```python
# 1. Mark 6 anatomical seams
# 2. ZEN UV auto_uv_unwrap
bpy.ops.uv.zenuv_auto_uv_unwrap(auto_detect_hard_edges=False, ... stretch=False, packing=True)
# 3. CONFORMAL inplace improvement (LSCM quality!)
bpy.ops.uv.zenuv_unwrap_inplace(urp_method='CONFORMAL', ...)
# 4. average_islands_scale
# 5. Normalize: margin + (uv - min)/(max-min) * (1-2*margin)
```
Result: **63.5% utilization, 2% margin** (or 70.5% if no CONFORMAL step).

## Summary

After exhaustive testing (>50 configurations across 7 approaches), the best
automated UV pipeline for QuadRemesher character meshes in Blender background
mode is:

**ZEN UV `auto_uv_unwrap` + `packing` + `average_islands_scale` + normalize with margin → 62-79% utilization, 8.25/10 quality**

## Final Configuration (2026-07-21)

```python
# 1. Mark 6 anatomical seams (back_center + L/R arm_inner + L/R leg_inner + neck_ring)
bpy.ops.mesh.mark_seam(clear=True)
# ... bmesh seam marking ...

# 2. ZEN UV auto_uv_unwrap
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.uv.zenuv_auto_uv_unwrap(
    auto_detect_hard_edges=False,  # NEVER True — shatters torso
    use_normal=False,
    use_texel_density=True,
    texel_density=10.0,
    TD_TextureSizeX=2048,
    TD_TextureSizeY=2048,
    mark_seam_edges=True,
    correct_self_intersecting=True,
    stretch=False,          # stretch=True times out on >50K faces
    packing=True,           # ZEN UV's own pack (better than Blender's)
    quads=False,            # quads=True crashes: needs preset dir
    cut=False,              # cut=True crashes: needs temp file path
)

# 3. Equalize texel density (head vs body)
bpy.ops.uv.average_islands_scale()

# 4. Normalize with margin (Python — 5% recommended)
margin = 0.05
scale = 0.90  # = 1.0 - 2*margin
uv_flat = np.zeros(nloops*2, dtype=np.float32)
uv.uv.foreach_get('vector', uv_flat)
us = uv_flat[0::2]; vs = uv_flat[1::2]
ru = max(us.max() - us.min(), 1e-6)
rv = max(vs.max() - vs.min(), 1e-6)
uv_flat[0::2] = margin + (us - us.min()) / ru * scale
uv_flat[1::2] = margin + (vs - vs.min()) / rv * scale
uv.uv.foreach_set('vector', uv_flat)
```

## Key Parameters

| Parameter | Value | Why |
|-----------|-------|-----|
| `auto_detect_hard_edges` | False | True shatters torso on organic models |
| `stretch` | False | True times out (>300s) on >50K faces |
| `packing` | True | Packs islands tightly (but 0% margin) |
| `quads` | False | True causes `[WinError 2]` file not found |
| `cut` | False | True causes `[WinError 2]` file not found |
| `texel_density` | 10.0 | Reasonable for 2K textures |
| margin | 0.05 | 5% provides safe gap between islands |
| scale | 0.90 | Compensates for margin |

## Seam Strategy (6 seams)

| Seam | Condition | Purpose |
|------|-----------|---------|
| Back center | X=mid, Y>0, Z=5%-95%H | Split front/back |
| Left arm inner | X<0, Y<0, Z=68%-84%H | Separate arm from body |
| Right arm inner | X>0, Y<0, Z=68%-84%H | Separate arm from body |
| Left leg inner | X=mid-1.5%W, Y<0, Z=2%-48%H | Separate leg |
| Right leg inner | X=mid+1.5%W, Y<0, Z=2%-48%H | Separate leg |
| **Neck ring** | X=mid, Z=80%-86%H | **Separate head from body** |

**Neck ring is critical**: Without it, the head and body are one island — the head gets excessive UV area (large checkerboard) while the body gets compressed. `average_islands_scale()` can only equalize per-island density; it cannot fix within-island distortion. The neck ring separates head into its own island so `average_islands_scale()` can properly balance head vs body texel density.

## Crashes & Avoid

| Operator | Result |
|----------|--------|
| `zenuv_unwrap(action='DEFAULT')` | EXCEPTION_ACCESS_VIOLATION on >50K faces |
| `zenuv_auto_uv_unwrap(quads=True)` | `[WinError 2]` — missing preset dir |
| `zenuv_auto_uv_unwrap(cut=True)` | `[WinError 2]` — missing preset dir |
| `zenuv_proxy_zenunwrap_all_selected(DEFAULT)` | 1/10 quality — auto-seam fails on QR |

## Tiny Island Cleanup (2892 → 6 islands)

After `zenuv_auto_uv_unwrap`, QR meshes produce ~2900 islands (10 large + ~2890 single-face).
These 2890 single-face islands consume UV space and can cause bake artifacts.
To merge them:

```python
# 1. Convert UV islands to seams
bpy.ops.uv.seams_from_islands()

# 2. Bmesh flood-fill to find all islands
bm = bmesh.from_edit_mesh(mesh.data)
# ... flood fill by seam connectivity ...
tiny_islands = [i for i in islands if len(i) <= 3]

# 3. Clear seam edges on tiny islands
for island in tiny_islands:
    for face in island:
        for edge in face.edges:
            if edge.seam:
                edge.seam = False

# 4. Re-unwrap (IMPORTANT: original anatomical seams are preserved on large islands)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', ...)
```

Result: **2902 islands → 6 islands, 0 tiny**.

**⚠️ CRITICAL WARNING**: After re-unwrapping, the ZEN UV unwrap quality is LOST.
The ANGLE_BASED re-unwrap produces severe stretching on head, arms, and legs.
**Recommendation**: Only use this if tiny islands cause bake artifacts.
Otherwise, keep the ZEN UV output with its 2890 single-face islands —
they only account for 3.2% of faces and don't affect bake quality significantly.

If you MUST merge tiny islands, re-mark ALL 6 anatomical seams before re-unwrapping
to minimize stretching. Even then, ANGLE_BASED quality is worse than ZEN UV's
original output. The root cause is that ZEN UV uses LSCM (CONFORMAL) which
handles cylindrical shapes (arms/legs/head) better than ANGLE_BASED.

### remove_doubles has no effect on QR meshes
Tested 0.001m, 0.005m, 0.01m — all result in 90333 to 90333 vertices (0 removed).
QR output is already continuous with 0 non-manifold edges and 0 duplicate
positions. The "vertex disconnect" the user sees is UV fragmentation illusion,
not actual mesh topology.

### UV islands touching edge after ZEN UV packing
ZEN UV's `packing=True` produces 0% margin — islands touch [0,1] boundaries.
Always normalize with margin (see step 4 above).

### GLB triangulates quads
`bpy.ops.export_scene.gltf()` always triangulates. Export BOTH GLB and OBJ:
```python
bpy.ops.wm.obj_export(filepath=out, export_selected_objects=True,
    export_materials=True, export_normals=False, export_uv=True)
```
OBJ preserves quad faces and includes .mtl material file.

## Expected Results

- Island count: 20-25 (manual seams) or 700-1200 (auto seams)
- UV utilization: 62-79% depending on margin
- Bake black pixels: 42-59% (limited by high-poly non-manifold geometry)
- Margin: 5% recommended for no bleeding