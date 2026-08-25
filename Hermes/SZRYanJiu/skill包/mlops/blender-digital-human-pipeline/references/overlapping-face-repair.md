# Overlapping Face Detection and Repair

> Date: 2026-08-01
> Context: User reported chest area geometry defects (small bumps/holes) on AI high-poly model after repair.

## Problem Types

| Type | Detection | Fix |
|------|-----------|-----|
| **Co-planar duplicate faces** (same position, same normal) | dot(normal) > 0.95 | Delete smaller area face |
| **Clothing-body parallel layers** (close, opposite normals) | dot(normal) < -0.95 | **DO NOT DELETE** — creates holes |
| **Floating fragments** (tiny isolated faces) | area < 0.01mm² | Delete + clean loose verts |
| **Local bumps from adhesion repair** | post-push deformation | Taubin smooth (λ=0.5, μ=-0.53) |

## Algorithm (remove_overlapping_faces)

```python
def remove_overlapping_faces(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bvh = BVHTree.FromBMesh(bm)
    
    faces_to_remove = set()
    overlap_count = 0
    
    # Scan ALL faces (not just first 30%) — chest area is in middle of vertex list
    for i in range(len(bm.faces)):
        f = bm.faces[i]
        center = f.calc_center_median()
        normal = f.normal.normalized()
        
        # Ray cast along normal to find parallel faces within 3mm
        hit = bvh.ray_cast(center + normal * 0.0001, normal, 0.003)
        if hit[0] is not None:
            hit_face = bm.faces[hit[2]]
            dot = normal.dot(hit_face.normal.normalized())
            
            if dot > 0.95:  # Co-planar duplicate
                # Keep larger face, delete smaller
                if f.calc_area() < hit_face.calc_area():
                    faces_to_remove.add(f.index)
                else:
                    faces_to_remove.add(hit_face.index)
                overlap_count += 1
            # dot < -0.95 (parallel layers) — skip, DO NOT DELETE
    
    # Delete with bmesh.ops.delete (avoids index table issues)
    if faces_to_remove:
        bm.faces.ensure_lookup_table()
        del_faces = [bm.faces[fi] for fi in faces_to_remove if fi < len(bm.faces)]
        bmesh.ops.delete(bm, geom=del_faces, context='FACES')
    
    # Clean loose vertices
    loose = [v for v in bm.verts if len(v.link_edges) == 0]
    for v in loose:
        bm.verts.remove(v)
    
    bm.to_mesh(obj.data)
    bm.free()
```

## Critical Rules

1. **Parallel layers (dot < -0.95) are clothing-body interfaces** — deleting them creates holes that expose skin. They are the AI model's inherent structure, not defects.

2. **Use `bmesh.ops.delete()` not `bm.faces.remove()`** — the latter causes `BMElemSeq[index]: outdated internal index table` errors.

3. **Scan ALL faces, not just first 30%** — chest area defects are in the middle of the vertex list (Z=1.25m on a 1.8m model).

4. **Floating fragment cleanup is separate** — `remove_overlapping_faces` only handles co-planar duplicates. Add a separate step for `area < 1e-8` faces.

5. **Taubin smooth after overlap removal** — removes local bumps from adhesion repair without shrinking the model (λ=0.5 shrink, μ=-0.53 inflate preserves volume).

## Results on Tripo Model (1.93M faces)

| Metric | Value |
|--------|-------|
| Overlap pairs detected | 666 |
| Co-planar duplicates removed | 11 |
| Parallel layers preserved | 655 |
| Scan time | 3.8s |
| Non-manifold after | 31 (< 50 threshold) |

## Integration Point

Add to `repair_pipeline` as step 6.5 (after fix_non_manifold_edges, before laplacian_smooth):

```python
print("\\n[6.5] Remove overlapping faces...")
stats["overlapping_removed"] = remove_overlapping_faces(obj)
```

Add Taubin smooth as step 7.5 (after laplacian_smooth):

```python
print("\\n[7.5] Taubin smooth (fix local bumps)...")
# λ=0.5 shrink → μ=-0.53 inflate (preserves volume)
bpy.ops.mesh.vertices_smooth_laplacian(repeat=1, lambda_factor=0.5)
bpy.ops.mesh.vertices_smooth_laplacian(repeat=1, lambda_factor=-0.53)
```
