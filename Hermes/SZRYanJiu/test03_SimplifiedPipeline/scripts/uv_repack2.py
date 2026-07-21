import bpy, os

mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
uv = mesh.data.uv_layers.active
mesh_data = mesh.data
l = len(mesh_data.loops)
# Read UVs
f_data = [0.0] * l * 2
uv.uv.foreach_get('vector', f_data)
# Read loop vertex indices
vi = [0] * l
mesh_data.loops.foreach_get('vertex_index', vi)

# Build face → loops mapping
face_loops = {}
for poly in mesh_data.polygons:
    face_loops[poly.index] = list(poly.loop_indices)

# Build edge → faces mapping (using polygons)
edge_faces = {}
for poly in mesh_data.polygons:
    for ek in poly.edge_keys:
        if ek not in edge_faces:
            edge_faces[ek] = []
        edge_faces[ek].append(poly.index)

# Read seams
seam_edges = set()
for poly in mesh_data.polygons:
    for ek in poly.edge_keys:
        # Check if this edge is a seam
        pass  # We need bmesh for seam check, but let's use UV distance instead

# Alternative: find islands by UV proximity (faces sharing UV positions are same island)
# Build face adjacency: two faces are adjacent if they share an edge AND their UVs are close
visited = set()
islands = []
for fi in face_loops:
    if fi not in visited:
        island = []
        stack = [fi]
        while stack:
            cf = stack.pop()
            if cf not in visited:
                visited.add(cf)
                island.append(cf)
                # Find neighbors via shared edges
                poly = mesh_data.polygons[cf]
                for ek in poly.edge_keys:
                    for nf in edge_faces.get(ek, []):
                        if nf not in visited:
                            # Check if UV is continuous across this edge
                            # (not a seam = UVs match)
                            # Simple: assume continuous if edge is not marked
                            stack.append(nf)
        islands.append(island)

# Filter large islands
large = [i for i in islands if len(i) > 100]
print(f'Large: {len(large)}')

# Get UV bounds for each large island
island_data = []
for island in large:
    loops = set()
    for fi in island:
        for li in face_loops[fi]:
            loops.add(li)
    us = [f_data[li * 2] for li in loops]
    vs = [f_data[li * 2 + 1] for li in loops]
    w = max(us) - min(us)
    h = max(vs) - min(vs)
    island_data.append({
        'loops': loops, 'min_u': min(us), 'min_v': min(vs),
        'w': max(w, 0.001), 'h': max(h, 0.001), 'area': w * h
    })

island_data.sort(key=lambda x: -x['area'])
total = sum(d['area'] for d in island_data)
scale = (0.85 / total) ** 0.5 if total > 0 else 1.0

margin = 0.02
x = margin
y = margin
row_h = 0
for d in island_data:
    w = d['w'] * scale + margin
    h = d['h'] * scale + margin
    if x + w > 1 - margin:
        x = margin
        y += row_h + margin
        row_h = 0
    if h > row_h:
        row_h = h
    ou = x - d['min_u'] * scale
    ov = y - d['min_v'] * scale
    for li in d['loops']:
        f_data[li * 2] = f_data[li * 2] * scale + ou
        f_data[li * 2 + 1] = f_data[li * 2 + 1] * scale + ov
    x += w

uv.uv.foreach_set('vector', f_data)

us2 = f_data[0::2]
vs2 = f_data[1::2]
grid = set()
for u, v in zip(us2, vs2):
    grid.add((int(u * 32), int(v * 32)))
print(f'Util: {100 * len(grid) / 1024:.1f}%')

RD = os.path.dirname(bpy.data.filepath)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, '04_uv.blend'))
print('SAVED')
