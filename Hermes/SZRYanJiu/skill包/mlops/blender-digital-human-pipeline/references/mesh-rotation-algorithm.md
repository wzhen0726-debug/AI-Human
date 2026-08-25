# Universal Mesh Rotation Algorithm (2026-07-31)

> Replaces the old `rotate_to_standard()` that only handled Tripo-default orientation.
> Works on ANY input orientation — no AI/ML, pure geometry.

## Problem

The old algorithm used bbox dimension ratios (`dim_y > dim_x * 1.8`) to detect
T/A-pose orientation. This failed when:
- User rotated the model before export
- Model had non-standard proportions (e.g., wide shoulders + narrow waist)
- Pre-existing `matrix_world` rotation (Hunyuan X-90°)

## Solution: 3-Step Geometric Pipeline

### Step 0: Clear pre-existing rotation
If `matrix_world` has rotation (Hunyuan GLB), apply it to vertex coordinates
and reset `matrix_basis` to identity.

### Step 1: `_ensure_stand_up(obj)`
Ensure height is along Z (largest bbox dim on Z axis).
- If `dim_y > dim_x` and `dim_y > dim_z`: rotate around X (+90°: y→-z, z→y)
- If `dim_x > dim_y` and `dim_x > dim_z`: rotate around Y (+90°: x→z, z→-x)
- If `dim_z` is already largest: no rotation needed

### Step 2: `_ensure_arms_along_x(obj)`
Ensure arms span along X (dim_x > dim_y * 1.5).
- If `dim_y > dim_x * 1.5`: rotate 90° around Z (x,y → y,-x)
- Otherwise: no rotation needed

### Step 3: `_detect_face_direction(obj)` + `_rotate_verts_90z()`
Detect which direction the face points, then rotate to -Y.

**Nasal protrusion method**: In the head region (Z > 85% of model height),
compute protrusion along each axis:
- `protrusion_+X = max(x_coords) - median(x_coords)`
- `protrusion_-X = median(x_coords) - min(x_coords)`
- `protrusion_+Y = max(y_coords) - median(y_coords)`
- `protrusion_-Y = median(y_coords) - min(y_coords)`

The direction with the highest protrusion is the face direction (nose sticks out).

Then rotate around Z to make face → -Y:
- `+X → -Y`: (x,y) → (y, -x)
- `-X → -Y`: (x,y) → (-y, x)
- `+Y → -Y`: (x,y) → (-x, -y) (180°)
- `-Y`: no rotation needed

## Verification

On user's resized+rotated Tripo T-pose (1.81m height):
- Initial: unknown orientation (user had rotated the GLB)
- After Step 1: standing (dim_z largest)
- After Step 2: arms along X (dim_x > dim_y * 1.5)
- After Step 3: face → -Y (protrusion_-Y = 0.047, highest)
- Final dims: x=1.801, y=0.313, z=1.810 ✅

## Implementation

All functions are in `repair.py`:
- `_detect_face_direction(obj)` → returns '+X', '-X', '+Y', '-Y', or None
- `_rotate_verts_90z(obj, direction)` → rotates verts to make face → -Y
- `_ensure_stand_up(obj)` → ensures height along Z
- `_ensure_arms_along_x(obj)` → ensures arms along X
- `rotate_to_standard(obj)` → orchestrates all steps

## Limitations

- Only handles 90° rotations (axis-aligned). Arbitrary angles (e.g., 45° tilt)
  would need PCA-based orientation detection — not implemented.
- Nasal protrusion assumes a human face with a nose. Non-human models or
  helmeted faces may detect wrong direction.
- If the model is already standing with arms along X but face on +Y (back
  to camera), only Step 3 rotates it 180°.
