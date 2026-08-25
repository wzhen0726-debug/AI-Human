# bmesh Geometry-Mirror While Keeping UV

How to mirror vertex positions in Blender without affecting UV maps or
textures. Verified against Blender 5.1 Python API docs (bmesh module).

## The Key Architectural Insight

Blender's mesh data stores vertex coordinates and UV coordinates on
**different elements**:

- `BMVert.co` — 3D world-space coordinates, stored on **vertices**
- `BMLoopUV.uv` — 2D UV coordinates, stored on **loops** (face corners,
  accessed via `bm.loops.layers.uv`)

Because these are independent custom-data layers, modifying `vert.co` does
**not** touch any UV layer. This is the foundation of the geometry-only mirror
approach — it's the closest Blender equivalent to ZBrush Smart Resymmetry.

## Relevant bmesh API (from docs.blender.org/api/current)

### BMVert (bmesh.types.BMVert)
- `co` — `mathutils.Vector`, 3D coordinates (read/write)
- `index` — int (may be dirty during editing; call `bm.verts.index_update()`)
- `link_loops` — loops that use this vertex (read-only)
- `normal` — vertex normal
- `copy_from(other)` — copy values from another vert of matching type

### BMLoopUV (bmesh.types.BMLoopUV)
- `uv` — `mathutils.Vector`, 2D UV coordinates
- `pin_uv` — bool, UV pin state

### Accessing UV layers
```python
uv_lay = bm.loops.layers.uv.active  # get active UV layer
for face in bm.faces:
    for loop in face.loops:
        uv = loop[uv_lay].uv        # UV on this loop (face corner)
        vert = loop.vert            # the vertex this loop references
        print("Vert:", vert.co[:])  # coordinate lives on vert, not loop
```

### bmesh.ops.symmetrize
```python
bmesh.ops.symmetrize(bm, input=[], direction='-X', dist=0, use_shapekey=False)
```
**Warning**: This operator creates NEW geometry (cuts, deletes, copies, merges).
New verts get new UV assignments. Do NOT use this if you want to preserve UV.
Use the manual vertex-coordinate approach instead.

## Working Script Template

```python
import bmesh
import mathutils

def mirror_geometry_keep_uv(obj, axis='X', threshold=0.0001, match_dist=0.001):
    """Mirror vertex positions along axis, preserving UV layers and materials.

    Args:
        obj: Blender object (must be mesh, in OBJECT mode)
        axis: 'X', 'Y', or 'Z'
        threshold: verts within this distance of axis plane are snapped to 0
        match_dist: max Y/Z distance for left-right vertex pairing

    Requires: topologically symmetric mesh (same vert count + connectivity
    on both sides of the axis).
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    other_axes = [i for i in range(3) if i != axis_idx]

    # 1. Partition verts: positive side, negative side, center
    pos_verts = [v for v in bm.verts if v.co[axis_idx] > threshold]
    neg_verts = [v for v in bm.verts if v.co[axis_idx] < -threshold]
    center_verts = [v for v in bm.verts if abs(v.co[axis_idx]) <= threshold]

    # 2. Build KDTree on negative side for fast nearest-neighbor matching
    kdtree = mathutils.kdtree.KDTree(len(neg_verts))
    for i, v in enumerate(neg_verts):
        # Match on the two non-mirror axes only
        co_2d = mathutils.Vector((v.co[other_axes[0]], v.co[other_axes[1]], 0))
        kdtree.insert(co_2d, i)
    kdtree.balance()

    # 3. For each positive-side vert, find nearest negative-side vert
    matched_neg = set()
    for pos_v in pos_verts:
        co_2d = mathutils.Vector(
            (pos_v.co[other_axes[0]], pos_v.co[other_axes[1]], 0))
        co_find, idx, dist = kdtree.find_nearest(co_2d)

        if idx is not None and dist < match_dist and idx not in matched_neg:
            neg_v = neg_verts[idx]
            matched_neg.add(idx)
            # Mirror: negate the axis coordinate, copy the other two
            neg_v.co[axis_idx] = -pos_v.co[axis_idx]
            neg_v.co[other_axes[0]] = pos_v.co[other_axes[0]]
            neg_v.co[other_axes[1]] = pos_v.co[other_axes[1]]

    # 4. Snap center verts to axis plane
    for v in center_verts:
        v.co[axis_idx] = 0.0

    # 5. Recalculate normals (geometry moved, normals may be stale)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # UV layers are untouched — they live on loops, not verts
    bm.to_mesh(obj.data)
    bm.free()

    # Update normals in depsgraph
    obj.data.update()
```

## Existing Plugin: mio3_symmetry

**mio3io/mio3_symmetry** — https://github.com/mio3io/mio3_symmetry

Blender addon (4.2+) that symmetrizes Meshes, Shape keys, Vertex weights, UV
Map, Normals, and Multires independently. Can be configured to symmetrize only
geometry while leaving UV untouched. Worth testing before writing a custom
script.

## Why Blender's Native Tools Don't Do This

| Tool | Creates new geometry? | UV behavior |
|------|----------------------|-------------|
| Mirror Modifier (applied) | Yes — duplicates verts/faces | UV copied or flipped (Flip UV option) |
| Symmetrize operator | Yes — cuts, deletes, copies, merges | New UVs generated for new geometry |
| bmesh.ops.symmetrize | Yes — same as UI operator | New UVs for new geometry |
| **Manual vert.co mirror** | **No — moves existing verts in-place** | **UV completely untouched** |

The manual approach is the only way to get ZBrush-like "move verts, keep UV"
behavior in Blender.

## Pitfalls

1. **Vertex matching is the bottleneck.** For meshes with 10k+ verts, use
   `mathutils.kdtree.KDTree` — never O(n²) nested loops.
2. **Topology must be symmetric.** If one side has extra verts/edges (e.g.
   from manual editing), matching will fail silently (unmatched verts stay
   in place). Check vertex counts on both sides first.
3. **Shape keys** are stored as offsets on verts (`bm.verts.layers.shape`).
   If shape keys exist, they must be mirrored separately or they'll be
   misaligned after geometry mirroring.
4. **Vertex groups** (deform weights) are also vert-attached. If the model
   is rigged, mirror vertex groups separately (they need .L/.R naming).
5. **Center verts** must be snapped to exactly 0 on the mirror axis, or
   you'll get a visible seam/gap.
6. **Normal recalculation** is needed after moving geometry — call
   `bmesh.ops.recalc_face_normals`.
