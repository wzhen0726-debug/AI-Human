"""Merge single-face UV islands into neighbors. Only 1-face islands."""
import bpy, bmesh, os

mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
if not mesh.data.uv_layers:
    mesh.data.uv_layers.new(name='UVMap')
bpy.context.scene.tool_settings.use_uv_select_sync = True

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.mark_seam(clear=True)

# ZEN UV auto_uv_unwrap
bpy.ops.uv.zenuv_auto_uv_unwrap(
    auto_detect_hard_edges=False, use_normal=False,
    use_texel_density=True, texel_density=10.0,
    TD_TextureSizeX=2048, TD_TextureSizeY=2048,
    mark_seam_edges=True, correct_self_intersecting=True,
    stretch=False, packing=True)

# Convert UV islands to seams
bpy.ops.uv.seams_from_islands()

# Find all islands via bmesh
bm = bmesh.from_edit_mesh(mesh.data)
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

# Only merge exact 1-face islands
merged = 0
for island in islands:
    if len(island) == 1:  # only single-face islands
        ff = island[0]
        for e in ff.edges:
            if e.seam:
                e.seam = False
                merged += 1

bmesh.update_edit_mesh(mesh.data)
print(f'Merged {merged} seam edges from 1-face islands')

# Re-unwrap (seams are now correct)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.005)
bpy.ops.uv.average_islands_scale()
bpy.ops.object.mode_set(mode='OBJECT')

# Add 5% margin
uv = mesh.data.uv_layers.active
l = len(mesh.data.loops)
f = [0.0] * l * 2
uv.uv.foreach_get('vector', f)
us = f[0::2]
vs = f[1::2]
min_u, max_u = min(us), max(us)
min_v, max_v = min(vs), max(vs)
ru = max(max_u - min_u, 1e-6)
rv = max(max_v - min_v, 1e-6)
m = 0.05
s = 0.90
for i in range(len(us)):
    f[i * 2] = m + (us[i] - min_u) / ru * s
    f[i * 2 + 1] = m + (vs[i] - min_v) / rv * s
uv.uv.foreach_set('vector', f)

# Stats
bpy.ops.object.mode_set(mode='EDIT')
bm2 = bmesh.from_edit_mesh(mesh.data)
bm2.faces.ensure_lookup_table()
visited2 = set()
islands2 = []
for face in bm2.faces:
    if face.index not in visited2:
        island = []
        stack = [face]
        while stack:
            cf = stack.pop()
            if cf.index not in visited2:
                visited2.add(cf.index)
                island.append(cf)
                for e in cf.edges:
                    if not e.seam:
                        for lf in e.link_loops:
                            if lf.face.index not in visited2:
                                stack.append(lf.face)
        islands2.append(island)
sizes = sorted([len(i) for i in islands2], reverse=True)
print(f'Islands: {len(islands2)} tiny(1): {sum(1 for s in sizes if s==1)} large(>100): {sum(1 for s in sizes if s>100)}')
print(f'Top5: {sizes[:5]}')
bpy.ops.object.mode_set(mode='OBJECT')

grid = set()
for u, v in zip(f[0::2], f[1::2]):
    grid.add((int(u * 32), int(v * 32)))
print(f'Util: {100 * len(grid) / 1024:.1f}%')

RD = os.path.dirname(bpy.data.filepath)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, '04_uv.blend'))
print('SAVED')
