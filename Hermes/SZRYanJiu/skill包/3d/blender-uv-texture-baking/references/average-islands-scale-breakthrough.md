# UV average_islands_scale Breakthrough (2026-07-20)

## Problem
All Blender UV methods (Smart UV, ANGLE_BASED, CONFORMAL, cylinder, xatlas) scored 2-3/10
on QuadRemesher output. Arms/legs had near-zero UV area; body had huge stretched patches.

## Root Cause
ANGLE_BASED/CONFORMAL unwrap assigns UV area proportional to **face count**, not 3D surface
area. On QR meshes where the body has more faces than arms/legs, the body gets huge UV space
while arms/legs get near-zero.

## Solution: `average_islands_scale()`

```python
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.005)

# CRITICAL: enable UV sync mode for background mode
bpy.context.scene.tool_settings.use_uv_select_sync = True

# THE KEY: equalizes texel density across all islands
bpy.ops.uv.average_islands_scale()

# Pack into [0,1] space
bpy.ops.uv.pack_islands(rotate=True, margin=0.005)
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Checker uniformity | 2/10 | 9.5/10 |
| Arms/legs visibility | 1.5/10 | 7.5/10 |
| Overall quality | 2/10 | 8.5/10 |
| Stretching | 3/10 | 9.0/10 |

## Seams Used (5 anatomical, works for any T-pose body type)

1. Back center: X≈mid_x, Y>0, Z∈[5%,95%]×H
2. Left arm inner: X<mid_x-W*0.12, Y<0, Z∈[68%,84%]×H
3. Right arm inner: X>mid_x+W*0.12, Y<0, Z∈[68%,84%]×H
4. Left leg inner: X≈mid_x-W*0.015, Y<0, Z∈[2%,48%]×H
5. Right leg inner: X≈mid_x+W*0.015, Y<0, Z∈[2%,48%]×H

Tolerance: xt = W*0.004 (very tight to avoid catching too many edges)

## Key API Discovery

`bpy.ops.uv.average_islands_scale()` and `bpy.ops.uv.pack_islands()` fail with
"context is incorrect" in `--background` mode even with `temp_override(area=IMAGE_EDITOR)`.

**Fix**: `bpy.context.scene.tool_settings.use_uv_select_sync = True` enables UV operators
directly from EDIT mode without needing an IMAGE_EDITOR area context.

This was tested on:
- Blender 5.1.0 (hash adfe2921d5f3)
- 90K-face Quad Remesher output
- T-pose character model

## Island Count Note
1145 islands remain (fragmentation is topology-driven from QR's uniform quads).
For BAKING, this is sufficient — each island correctly receives high-poly texture data.
For direct texture painting, would need RizomUV or manual seam marking in UI.
