# Sculpt Smooth as bmesh Laplacian (Regional, Background-safe)

## When
User confirms "GUI sculpt smooth brush fixes the bump" on a specific body region
(e.g. chest clothes-body junction, z≈1.20-1.40m). Background mode cannot drive
`bpy.ops.sculpt.sculptmode_toggle()` + paint operators reliably without context
overrides. Implement the brush math directly with bmesh.

## Pattern
Regional Laplacian smooth: for each vertex in the target region, lerp toward
centroid of its edge-neighbors. Iterate N times.

```python
def sculpt_smooth_region(obj, z_range=(1.20, 1.40), iterations=5, strength=0.3):
    import bmesh
    from mathutils import Vector
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    z_min, z_max = z_range
    target = [v for v in bm.verts if z_min <= v.co.z <= z_max]
    if not target:
        bm.free(); return
    for _ in range(iterations):
        new_coords = {}
        for v in target:
            nb = [e.other_vert(v) for e in v.link_edges]
            if not nb: continue
            avg = sum((n.co for n in nb), Vector()) / len(nb)
            new_coords[v.index] = v.co.lerp(avg, strength)
        for v in target:
            if v.index in new_coords: v.co = new_coords[v.index]
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
```

## Tuning
- `iterations=5, strength=0.3`: conservative — removes 1-2mm bumps without
  collapsing clothes wrinkles.
- `iterations=8, strength=0.5`: aggressive — flattens larger bumps but risks
  losing anatomical detail and creating boundary edges.
- Start conservative, increase only if user reports bump still visible.

## Pitfall: Boundary edges after regional smooth
Regional smooth moves interior verts but leaves boundary verts at original
positions → tiny holes (5-10 boundary edges observed at iterations=8, strength=0.5).
**Always follow with**:
```python
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.fill_holes(sides=0)
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.object.mode_set(mode='OBJECT')
```

## Why not bpy.ops.sculpt
- `bpy.ops.sculpt.sculptmode_toggle()` needs an active tool context that
  `--background --factory-startup` does not populate.
- Paint operators (`bpy.ops.paint.brush_select`, `bpy.ops.sculpt.brush_stroke`)
  require stroke event data (pressure, location) that cannot be synthesized
  without a real tablet/mouse input.
- Vertex-group masked sculpt also requires GUI-mode operator dispatch.
- bmesh Laplacian is mathematically equivalent to the Smooth brush (unweighted
  umbrella) and runs in ~2s for the chest region on a 2M-face mesh.

## Region selection heuristic
For AI-generated clothes-body junctions (Tripo, etc.), abnormal bumps cluster
at z=1.20-1.40m (chest) and z=0.70-0.85m (waist) on a 1.8m T-pose standing
model. Diagnose with BVH overlap scan first — only smooth where overlap pairs
concentrate. Do NOT smooth hands/face (loses detail).