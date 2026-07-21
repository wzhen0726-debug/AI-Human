import bpy, bmesh, os

mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
uv = mesh.data.uv_layers.active
l = len(mesh.data.loops)
f_data = [0.0] * l * 2
uv.uv.foreach_get('vector', f_data)

bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.faces.ensure_lookup_table()
visited = set()
islands = []
for face in bm.faces:
    if face.index not in visited:
        island = []
        stack = [face]
        while stack:
            cf = stack.pop()
            if cf.index not in visited:
                visited.add(cf.index)
                island.append(cf)
                for e in cf.edges:
                    if not e.seam:
                        for lf in e.link_loops:
                            if lf.face.index not in visited:
                                stack.append(lf.face)
        islands.append(island)
bm.free()

large = [i for i in islands if len(i) > 100]
print(f'Large: {len(large)} sizes: {sorted([len(i) for i in large], reverse=True)}')

margin = 0.02
island_data = []
for island in large:
    loops = set()
    for ff in island:
        for loop in ff.loops:
            loops.add(loop.index)
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
