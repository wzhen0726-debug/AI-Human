# MetaHuman Body Wrap — T-pose Alignment & UV Transfer

## Core Goal
WRAP transfers MetaHuman topology + UV, NOT surface fitting.

## Complete Pipeline

### 1. Import Mixamo T-pose FBX
Armature scale=0.01 (cm). Fix: `arm.scale=(100,100,100)`, `transform_apply`.

### 2. Apply Armature Animation
T-pose at frame 2: `frame_set(2)`, `modifier_apply("Armature")`.

### 3. Delete Armature
Remove actions, armature object, armature data.

### 4. Vertex-Level Transform (CRITICAL)
Blender 5.1 `rotation_euler`/`matrix_basis` unreliable — use `v.co` directly.
Original: X=arms, Y=height, Z=depth. Target: X=arms, Y=depth, Z=height.
```python
v.co.x = x*0.01; v.co.y = -z*0.01; v.co.z = y*0.01
```

### 5. Pure Scale+Translate Alignment
DO NOT use RBF/Shrinkwrap/affine. Match bbox spans:
```python
sx = tripo_xspan / mh_xspan
v.co = (v.co - center)*scale + tripo_center
```

### 6. UV Preserved
Only `v.co` changes. UV data untouched.

## Failed Methods
- Shrinkwrap: collapse on clothes
- RBF (all): global distortion
- Affine: axis mixing
- ARAP: 14 disconnected components