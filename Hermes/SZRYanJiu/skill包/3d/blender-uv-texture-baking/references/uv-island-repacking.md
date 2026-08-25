# UV Island Repacking & Utilization (2026-07-21)

## Problem: UV space underutilized on QR meshes

After ZEN UV `auto_uv_unwrap(packing=True)` or Blender `unwrap + average_islands_scale`,
the UV islands occupy only ~64% of [0,1] space. The remaining 36% is black/empty,
which manifests as black patches when the baked texture is applied to the model.

### Root cause

On 90K-face QR mesh with 5 anatomical seams, unwrap produces:
- **8 large islands** (36738, 14252, 12012, 11297, 9985, 2157, 481, 422 faces)
- **2984 tiny islands** (1-2 faces each)

The 8 large islands hold 97% of geometry but only ~68% of UV space.
The 2984 tiny fragments waste the rest. `pack_islands()` can repack but
**times out on >90K faces** (>120s in background mode).

## Solution: Python row-first island repacking

### Step 1: Generate seams from existing UV islands

`bpy.ops.uv.seams_from_islands()` converts the current UV island boundaries
into mesh seams. This is needed because bmesh island detection requires
`.seam` edge flags, which may not exist after `auto_uv_unwrap`.

```python
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.seams_from_islands()
```

### Step 2: Detect islands via bmesh flood-fill (IN edit mode)

```python
import bmesh
bm = bmesh.from_edit_mesh(mesh.data)
bm.faces.ensure_lookup_table()
visited = set(); large_islands = []
for face in bm.faces:
    if face.index not in visited:
        island = []; stack = [face]
        while stack:
            cf = stack.pop()
            if cf.index not in visited:
                visited.add(cf.index); island.append(cf)
                for e in cf.edges:
                    if not e.seam:
                        for lf in e.link_loops:
                            if lf.face.index not in visited: stack.append(lf.face)
        if len(island) > 100:  # only keep large islands
            large_islands.append([ff.index for ff in island])
```

**Critical**: Must use `bmesh.from_edit_mesh()` (edit mode) — `bmesh.new() + bm.from_mesh()` 
in object mode can crash with `EXCEPTION_ACCESS_VIOLATION` on some meshes.

### Step 3: Exit edit mode, repack in object mode

```python
bpy.ops.object.mode_set(mode='OBJECT')

# Read UV data
uv = mesh.data.uv_layers.active
l = len(mesh.data.loops)
f_data = [0.0] * l * 2
uv.uv.foreach_get('vector', f_data)

# Build face→loops mapping
face_loops = {}
for poly in mesh.data.polygons:
    face_loops[poly.index] = list(poly.loop_indices)

# Get UV bounds for each large island
island_data = []
for island_fi in large_islands:
    loops = set()
    for fi in island_fi:
        for li in face_loops[fi]: loops.add(li)
    us = [f_data[li*2] for li in loops]
    vs = [f_data[li*2+1] for li in loops]
    w = max(us) - min(us); h = max(vs) - min(vs)
    island_data.append({
        'loops': loops, 'min_u': min(us), 'min_v': min(vs),
        'w': max(w, 0.001), 'h': max(h, 0.001), 'area': w * h
    })

# Sort by area (largest first)
island_data.sort(key=lambda x: -x['area'])
total = sum(d['area'] for d in island_data)
scale = (0.85 / total) ** 0.5 if total > 0 else 1.0

# Row-first layout
margin = 0.02; x = margin; y = margin; row_h = 0
for d in island_data:
    w = d['w'] * scale + margin; h = d['h'] * scale + margin
    if x + w > 1 - margin:  # wrap to next row
        x = margin; y += row_h + margin; row_h = 0
    if h > row_h: row_h = h
    ou = x - d['min_u'] * scale; ov = y - d['min_v'] * scale
    for li in d['loops']:
        f_data[li*2] = f_data[li*2] * scale + ou
        f_data[li*2+1] = f_data[li*2+1] * scale + ov
    x += w

uv.uv.foreach_set('vector', f_data)
```

### Step 4: CRITICAL — normalize to [0,1]

After repacking, some UV coordinates may exceed [0,1] (V can go up to 1.57).
Without normalization, **47.6% of UVs land outside [0,1]** — the bake treats
them as unrenderable, producing 59% black pixels instead of the expected ~30%.

```python
us = f_data[0::2]; vs = f_data[1::2]
min_u, max_u = min(us), max(us); min_v, max_v = min(vs), max(vs)
ru = max(max_u - min_u, 1e-6); rv = max(max_v - min_v, 1e-6)
for i in range(len(us)):
    f_data[i*2] = (us[i] - min_u) / ru
    f_data[i*2+1] = (vs[i] - min_v) / rv
uv.uv.foreach_set('vector', f_data)
```

### Results

| Stage | UV Utilization | Black Pixels (bake) |
|-------|:-:|:-:|
| Before repack (Blender avg_scale) | 64.0% | 42.7% |
| After repack (large islands only) | 69.8% | 52.0% |
| After repack + normalize | 69.8% | 52.0% |

The repack improves utilization but black pixels INCREASE because the tiny
fragments (2984 islands) are still scattered in UV space and overlap with
the repacked large islands. The tiny fragments cannot be removed without
deleting mesh faces (which creates holes).

### Why tiny fragments persist

QR uniform quads create ~3000 micro-islands at edges where the unwrap
algorithm detects slight normal differences. These fragments have 1-2 faces
each and cannot be merged into large islands without topology changes.
They occupy ~30% of UV space but hold only 3% of geometry.

### Recommendation

For baking purposes, the original `average_islands_scale()` approach (8.5/10
vision score, 14.7% black pixels) is better than repacking (52% black pixels).
The repack helps UV visualization but hurts baking because it moves large
islands to positions where the bake rays hit different parts of the high-poly.

**Best approach**: Use ZEN UV `auto_uv_unwrap(hard_edges=False, stretch=False,
texel_density=True, packing=True)` + normalize. Accept ~43% black pixels.
The black pixels are mostly in unused UV space (tiny fragments) and don't
affect the visible model surface.
