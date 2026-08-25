# Mesh Orientation Correction — foot_score Height-Axis Detection

> Discovered 2026-08-01 during v3_QuadRemesher pipeline step 01.
> Symptom: After user rotated raw_model.glb, repair output was lying down (visual check) but bbox dims appeared "standing" (x≈z).

## Problem

AI-generated human meshes arrive in arbitrary orientations. The goal is: **stand up (height→Z), face→-Y, arms→X**.

Naive bbox approaches fail because **arm-span ≈ height** on a T-pose human (1.81m vs 1.80m). When the model is rotated, the X and Z dimensions are nearly equal, and the algorithm can't tell which axis is the height.

## Failed Approaches (with reasons)

1. **"Largest bbox dimension = height"** — arm-span (1.81m) ≈ height (1.80m), X≈Z, indistinguishable.
2. **"Bottom 1% verts spread small = standing"** — both hands and feet have similar spread at their respective ends; the signature is not unique.
3. **Manual angle input** — user said "don't hardcode from my data, the rotation will change."

## Solution: foot_score (cross-section area comparison)

**Key insight**: The cross-section at the **foot end** (foot + lower leg) is much larger than at the **wrist end** (hand). The axis where "low-end area - high-end area" is largest is the height axis.

```python
def end_area(axis_vals, other1, other2, at_low):
    """Cross-sectional area at one end of an axis."""
    s = sorted(axis_vals)
    n = max(200, len(s) // 100)
    t = s[n] if at_low else s[-n]
    o1 = [v for v, a in zip(other1, axis_vals) if (a <= t if at_low else a >= t)]
    o2 = [v for v, a in zip(other2, axis_vals) if (a <= t if at_low else a >= t)]
    if not o1 or not o2:
        return 0
    return (max(o1) - min(o1)) * (max(o2) - min(o2))

def foot_score(axis_vals, o1, o2):
    """How much does the low end look like a foot?"""
    return end_area(axis_vals, o1, o2, True) - end_area(axis_vals, o1, o2, False)

# For each axis X, Y, Z:
score_x = foot_score(xs, ys, zs)  # X as height axis
score_y = foot_score(ys, xs, zs)  # Y as height axis
score_z = foot_score(zs, xs, ys)  # Z as height axis

height_axis = max([("X", score_x), ("Y", score_y), ("Z", score_z)], key=lambda t: t[1])[0]
```

**Verified on Tripo resized model**: scores x=-0.000, y=-0.583, **z=+0.097** → correctly identifies height along Z (already standing), no false "stand up" rotation.

## Foot Direction (low vs high end)

After finding the height axis, determine which end is the foot:

```python
def foot_at_low(axis_vals, o1, o2):
    return end_area(axis_vals, o1, o2, True) > end_area(axis_vals, o1, o2, False)
```

Rotate so foot goes to -Z. For height along X:
- Foot at -X → rotate Y+90° (x→z, z→-x)
- Foot at +X → rotate Y-90° (x→-z, z→x)

## Face Direction Detection (nose protrusion)

Once standing and arms along X, detect face direction by nose protrusion in the face zone (top 15% of height):

```python
import statistics

z_face = min_z + height * 0.85
fx = [v.co.x for v in mesh.data.vertices if v.co.z >= z_face]
fy = [v.co.y for v in mesh.data.vertices if v.co.z >= z_face]

mx = statistics.median(fx)
my = statistics.median(fy)

directions = {
    "+X": max(fx) - mx,  # nose protrusion in +X
    "-X": mx - min(fx),  # nose protrusion in -X
    "+Y": max(fy) - my,  # nose protrusion in +Y
    "-Y": my - min(fy),  # nose protrusion in -Y
}
face_dir = max(directions, key=directions.get)
```

Then rotate around Z to bring face to -Y:
- `+X` → rotate Z clockwise 90° (x,y)→(y,-x)
- `-X` → rotate Z counterclockwise 90° (x,y)→(-y,x)
- `+Y` → rotate Z 180° (x,y)→(-x,-y)
- `-Y` → no rotation needed

**Pitfall**: The `+Y` branch must actually rotate 180° (not `pass`). A missing rotation here leaves the model facing backwards.

## Verification Protocol (MANDATORY)

After implementing orientation changes, **always verify with rendering + vision_analyze**, not just bbox dims:

1. Render from -Y direction (should see face if face→-Y)
2. Ask vision: "Do you see a face or back of head? Standing or lying? Arms spread?"
3. Expect: face, standing, arms spread horizontally

**Never trust bbox dims alone** — arm-span ≈ height makes dims ambiguous.

## Integration in repair.py

```python
def rotate_to_standard(obj):
    # 1. Clear pre-existing matrix_world rotation
    # 2. _ensure_stand_up(obj) — foot_score axis detection + rotation
    # 3. _ensure_arms_along_x(obj) — if arms along Y, rotate Z 90°
    # 4. _detect_face_direction(obj) — nose protrusion
    # 5. _rotate_verts_90z(obj, face_dir) — rotate to -Y
```

## Files

- Working implementation: `v3_QuadRemesher_交付/01高模修复与黏连检测/scripts/repair.py` (functions `_ensure_stand_up`, `_detect_face_direction`, `_rotate_verts_90z`, `rotate_to_standard`)
- Verification renders: `01高模修复与黏连检测/screenshots/loop1_negY.png`
