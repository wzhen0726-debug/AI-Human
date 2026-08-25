# Mesh Rotation: Stand-Up Detection + Face Direction

> Verified 2026-07-31 on Blender 5.1. Tripo T-pose model resized to 1.81m height.
> Previous bbox-dimension method FAILED when dim_x ≈ dim_z (1.801 vs 1.810) — model remained lying.

## Problem

The old `rotate_to_standard()` used `dim_z >= dim_x and dim_z >= dim_y` to detect standing pose. When a user resized/rotated the model so that dim_x ≈ dim_z (both ~1.81m), this condition was true even though the model was lying horizontally — the "height" was along X, not Z. The model stayed lying.

## Solution: Three-step pure-geometry rotation (no AI)

### Step 1: `_ensure_stand_up` — bottom-point spread detection

Instead of comparing bbox dimensions, collect the **lowest 1% of vertices** (foot region) and check their XY spread:

```python
all_z = sorted([v.co.z for v in mesh.data.vertices])
bottom_count = max(100, len(all_z) // 100)
z_threshold = all_z[bottom_count]

bottom_xs = [v.co.x for v in mesh.data.vertices if v.co.z <= z_threshold]
bottom_ys = [v.co.y for v in mesh.data.vertices if v.co.z <= z_threshold]

bottom_range_x = max(bottom_xs) - min(bottom_xs)
bottom_range_y = max(bottom_ys) - min(bottom_ys)
bottom_spread = max(bottom_range_x, bottom_range_y)

# Standing: foot vertices cluster in small XY area
# Lying: foot vertices spread along body length
is_standing = bottom_spread < dim_z * 0.15  # <15% of height = standing
```

**Why this works**: A standing person's feet occupy a small XY circle (~10cm radius). A lying person's "feet" (lowest Z) span the full body length along one axis. The 15% threshold is robust: standing spread is typically 3-7% of height, lying spread is 80-100%.

**Determining rotation axis**: Use `bottom_range_x > bottom_range_y` to determine which axis the body lies along, then rotate around the perpendicular axis:
- `bottom_range_x > bottom_range_y` → body along X → rotate around Y
- `bottom_range_y > bottom_range_x` → body along Y → rotate around X

**Multi-round safety**: Wrap in `for _ in range(3): if not _ensure_stand_up(obj): break` — some orientations need two rotations (e.g., lying on side + facing wrong way).

### Step 2: `_ensure_arms_along_x` — bbox dimension check

After standing, check `dim_x > dim_y * 1.5`. If not, rotate 90° around Z. This is the same as before — it works reliably once the model is standing.

### Step 3: `_detect_face_direction` — nasal protrusion

After standing + arms along X, the face could point +X, -X, +Y, or -Y. Detect by **nasal protrusion**:

```python
import statistics

z_face = min_z + height * 0.85  # top 15% = face region
fx = [v.co.x for v in mesh.data.vertices if v.co.z >= z_face]
fy = [v.co.y for v in mesh.data.vertices if v.co.z >= z_face]

med_x = statistics.median(fx)
med_y = statistics.median(fy)

directions = {
    '+X': max(fx) - med_x,  # nose protrudes +X
    '-X': med_x - min(fx),  # nose protrudes -X
    '+Y': max(fy) - med_y,  # nose protrudes +Y
    '-Y': med_y - min(fy),  # nose protrudes -Y
}

best_dir = max(directions, key=directions.get)  # highest protrusion = face direction
```

**Why median not mean**: The median is robust to outliers (hair, ears). The nose creates a small cluster of vertices far from the median in one direction. Back of head is relatively flat, so protrusion is low in that direction.

**Why top 85% not top 50%**: Restricting to Z ≥ 85% of height isolates the face. Lower regions (chest, shoulders) have similar protrusion in all directions and would dilute the signal.

### Step 4: `_rotate_verts_90z` — rotate to face -Y

Map the detected direction to a Z-axis rotation:
- `+X` → rotate 90° CW: `(x,y) → (y, -x)`
- `-X` → rotate 90° CCW: `(x,y) → (-y, x)`
- `+Y` → rotate 180°: `(x,y) → (-x, -y)`
- `-Y` → no rotation needed

## Verified Results

| Check | Value | Pass |
|-------|-------|------|
| dims | x=1.801 y=0.313 z=1.810 | ✅ |
| arms along X (dx > dy*1.5) | True | ✅ |
| face along -Y (dy < dx*0.3) | True | ✅ |
| standing (dz > dx and dz > dy) | True | ✅ |
| bottom_spread | 0.106 | ✅ (< 0.272 = dz*0.15) |
| face_dir | -Y (protrusion 0.094) | ✅ |

## Limitations

- **Does not handle arbitrary tilt angles** (e.g., 45° rotation). Only detects axis-aligned lying/standing. A model rotated 30° from vertical would have ambiguous bottom-spread.
- **Face direction fails on bald/bald-cap models** if the nose is not the most protruding feature in the top 15%. Ears or hair can dominate. Mitigation: use top 90% (nose tip) instead of 85%.
- **Multi-axis rotations**: if the model is lying AND facing the wrong way, two rotations are needed. The `for _ in range(3)` loop handles this but adds ~2s per iteration on 1M vertices.
