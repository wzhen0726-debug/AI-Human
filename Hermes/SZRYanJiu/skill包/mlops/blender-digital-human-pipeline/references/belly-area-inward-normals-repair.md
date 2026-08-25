# Belly/Surface Inward-Normal Repair

## Problem
AI-generated high-poly models (Tripo, etc.) can have patches of **inward-facing normals** on the body surface — typically in the belly/abdomen area (z≈0.90~0.97, x≈-0.12~0.12, y<0 for front). These create a **visual "hole" illusion**: the surface appears as a dark puncture/break with a raised rim, even though the mesh is fully watertight (no boundary edges).

## Diagnosis
- **Not a real hole**: boundary edges = 0 in the affected area
- **Not an overlap**: no co-planar reverse-parallel layers
- **Root cause**: 1000-5000+ faces with normals pointing toward the model interior (dot product < 0 with outward-facing direction)
- **Location** (for this model): z=0.90~0.97, x=-0.12~0.12, y<-0.02 (front belly)

## Fix: Local Normal Flip
```python
import bpy, bmesh
from mathutils import Vector

bm = bmesh.new()
bm.from_mesh(obj.data)
bm.faces.ensure_lookup_table()

center = Vector((0, 0, 0.93))  # zone center

# Find inward-facing faces in the affected zone
inward = [f for f in bm.faces
    if -0.12 <= f.calc_center_median().x <= 0.12
    and 0.90 <= f.calc_center_median().z <= 0.97
    and f.calc_center_median().y < -0.02
    and f.normal.dot(f.calc_center_median() - center) < 0]

# Flip them
for f in inward:
    f.normal_flip()

bm.to_mesh(obj.data)
bm.free()
obj.data.update()
```

## Verification
- Count inward faces before/after: should go from N to 0
- Non-manifold edges and boundary edges should remain unchanged
- Render the area from a front-facing perspective to confirm the "hole" is gone

## Pitfalls
- DO NOT use global `normals_make_consistent` — the multi-layer structure (clothes inner-surface, body, etc.) has legitimate inward normals that will be incorrectly flipped
- DO NOT use sculpt smooth / Laplacian — the geometry is correct, only the normals are wrong
- The fix is purely a normal operation — no vertex displacement, no face deletion, no topology change