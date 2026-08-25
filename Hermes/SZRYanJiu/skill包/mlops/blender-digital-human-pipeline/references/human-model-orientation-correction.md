# Human Model Orientation Correction — foot_score Cross-Section Method

> Verified 2026-07-31 on Tripo T-pose (1.93M faces) + Blender 5.1, vision-confirmed.
> Algorithm is fully offline (pure geometry) — vision_analyze is used ONLY for verification, never for the correction itself.

## Problem

AI-generated human models arrive in arbitrary orientations: lying down, facing +X/+Y, rotated 90°, or with a pre-baked `matrix_world` rotation (e.g. Hunyuan X-90°). The pipeline requires a canonical pose: **standing (height along Z), arms along X, face toward -Y, feet at Z=0**.

## Why bbox-dims comparison fails (the core pitfall)

The naive approach "height axis = the largest bbox dimension" **breaks on T-pose humans** because arm-span ≈ height:

| Model | dim_x | dim_y | dim_z |
|-------|-------|-------|-------|
| Tripo T-pose (standing, face +Y) | 1.810 (arm span) | 0.313 (thickness) | 1.801 (height) |

dim_x and dim_z differ by only 0.5%. Any "largest dim = height" rule is a coin flip. A previous version then tried "rotate to stand up from X" and **laid the already-standing model down**.

A second naive approach — "feet are the lowest 1% of vertices along Z; standing if their XY spread is small" — also fails: after the model is lying down, the "bottom" vertices along the *arm* axis have a small spread too (hands are compact), producing a false "already standing" verdict.

## The foot_score method (works)

**Key insight**: the foot end of the height axis has a much larger cross-sectional area (foot + lower leg) than the wrist end (hand + wrist). The arm axis has hands at BOTH ends (similar small cross-sections). So:

For each candidate axis (X, Y, Z):
1. Take the lowest 1% of vertices at BOTH ends of that axis.
2. Compute each end's cross-sectional area = (range in axis₂) × (range in axis₃).
3. `foot_score(axis) = area(low end) − area(high end)`.
4. **Height axis = the axis with the largest foot_score** (feet are big, hands are small → large positive difference).

```python
def end_area(axis_vals, other1, other2, at_low):
    s = sorted(axis_vals)
    n = max(200, len(s)//100)
    t = s[n] if at_low else s[-n]
    o1 = [v for v, a in zip(other1, axis_vals) if (a <= t if at_low else a >= t)]
    o2 = [v for v, a in zip(other2, axis_vals) if (a <= t if at_low else a >= t)]
    if not o1 or not o2: return 0
    return (max(o1)-min(o1)) * (max(o2)-min(o2))

def foot_score(axis_vals, o1, o2):
    return end_area(axis_vals, o1, o2, True) - end_area(axis_vals, o1, o2, False)

# Tripo T-pose measured: foot_scores x=-0.000, y=-0.583, z=+0.097 → height = Z (already standing ✓)
```

## Foot-end polarity (which end is feet)

Once the height axis is known, determine whether feet are at the low or high end:

```python
foot_at_low = end_area(axis_vals, o1, o2, True) > end_area(axis_vals, o1, o2, False)
```

Then rotate so feet land at **-Z**:
- Height along X, foot at low (-X) → rotate +90° around Y: `x→z, z→-x`
- Height along X, foot at high (+X) → rotate -90° around Y: `x→-z, z→x`
- Height along Y, foot at low (-Y) → rotate -90° around X: `y→z, z→-y`
- Height along Y, foot at high (+Y) → rotate +90° around X: `y→-z, z→y`

## Face direction (nose protrusion)

After standing + arms-along-X, detect which horizontal direction the face points by sampling the **nose protrusion** in the head region (top 15% of height):

```python
z_face = min_z + height * 0.85
head_x = [v.co.x for v in verts if v.co.z >= z_face]
head_y = [v.co.y for v in verts if v.co.z >= z_face]
import statistics
mx, my = statistics.median(head_x), statistics.median(head_y)
dirs = {"+X": max(head_x)-mx, "-X": mx-min(head_x),
        "+Y": max(head_y)-my, "-Y": my-min(head_y)}
face_dir = max(dirs, key=dirs.get)   # nose protrudes most toward the face direction
```

Then rotate around Z to bring the face to -Y:
- `+X` → rotate -90° around Z: `x→y, y→-x`
- `-X` → rotate +90° around Z: `x→-y, y→x`
- `+Y` → rotate 180° around Z: `x→-x, y→-y`
- `-Y` → no rotation

**Gotcha that shipped to production once**: the rotation function's `direction` parameter means "where the face CURRENTLY points", not "target direction". A `+Y: pass` branch (treating it as already-correct) silently skipped the 180° turn and the model stayed facing +Y. Name the parameter `current_face_dir` to avoid this trap.

## Pre-existing matrix_world rotation (Hunyuan)

Some exporters (Hunyuan) bake a rotation into `obj.matrix_world` (e.g. X-90°) instead of vertex coordinates. Apply it to verts FIRST, then reset:

```python
if abs(obj.matrix_world.to_euler().x) > 0.01 or abs(obj.matrix_world.to_euler().y) > 0.01:
    rot = obj.matrix_world.to_3x3()
    for v in bm.verts: v.co = rot @ v.co
    obj.matrix_basis = Matrix.Identity(4)  # NOT rotation_euler — unreliable in Blender 5.1
```

## Full correction sequence

```
1. Clear pre-baked matrix_world rotation (apply to verts, reset matrix_basis)
2. foot_score → find height axis → rotate to stand (height → Z, feet → -Z)
3. Check arms along X (dim_x > dim_y * 1.5); if not, rotate 90° around Z
4. Nose protrusion → face direction → rotate around Z to face -Y
5. Center on origin, feet at Z=0
```

## Verification — NEVER trust bbox dims alone

User corrected this repeatedly ("你不自查的吗"). After ANY orientation change:

1. **Render** the result from the -Y direction (and ideally +X side view) with Workbench/Studio shading.
2. **vision_analyze** the render and ask three questions: standing or lying? face or back of head? arms spread horizontally?
3. Only proceed when vision confirms all three. `vision_analyze` times out often — wait 45-60s and retry; it has ~20 free calls/day so use it for verification milestones, not per-iteration.

Numeric checks that ARE meaningful after vision confirmation: `dim_x > dim_y*1.5` (arms along X), `dim_z > dim_y*1.5 and dim_z > dim_x*0.85` (standing; the 0.85 not 1.1 because arm-span can slightly exceed height).
