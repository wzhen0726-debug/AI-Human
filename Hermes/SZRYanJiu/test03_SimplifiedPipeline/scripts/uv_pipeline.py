"""UV pipeline: seams + auto_uv_unwrap + merge 1-face + CONFORMAL + relax + average + 2%"""
import bpy, bmesh, os

mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
if not mesh.data.uv_layers: mesh.data.uv_layers.new(name='UVMap')
bpy.context.scene.tool_settings.use_uv_select_sync = True

# 1. Mark seams
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.mark_seam(clear=True)
bm = bmesh.from_edit_mesh(mesh.data)
xs = [v.co.x for v in bm.verts]; zs = [v.co.z for v in bm.verts]
min_x, max_x = min(xs), max(xs); min_z, max_z = min(zs), max(zs)
mid_x = (min_x + max_x) / 2; H = max_z - min_z; W = max_x - min_x; xt = W * 0.003
for e in bm.edges:
    v0, v1 = e.verts; m = (v0.co + v1.co) / 2
    if abs(v0.co.x - mid_x) < xt * 2 and abs(v1.co.x - mid_x) < xt * 2 and min_z + H * 0.80 < m.z < min_z + H * 0.86: e.seam = True
    elif abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and v0.co.y > 0 and v1.co.y > 0 and min_z + H * 0.05 < m.z < min_z + H * 0.95: e.seam = True
    elif v0.co.x < mid_x - W * 0.12 and v1.co.x < mid_x - W * 0.12 and v0.co.y < 0 and v1.co.y < 0 and min_z + H * 0.68 < m.z < min_z + H * 0.84: e.seam = True
    elif v0.co.x > mid_x + W * 0.12 and v1.co.x > mid_x + W * 0.12 and v0.co.y < 0 and v1.co.y < 0 and min_z + H * 0.68 < m.z < min_z + H * 0.84: e.seam = True
    elif abs(v0.co.x - (mid_x - W * 0.015)) < xt and abs(v1.co.x - (mid_x - W * 0.015)) < xt and v0.co.y < 0 and v1.co.y < 0 and min_z + H * 0.02 < m.z < min_z + H * 0.48: e.seam = True
    elif abs(v0.co.x - (mid_x + W * 0.015)) < xt and abs(v1.co.x - (mid_x + W * 0.015)) < xt and v0.co.y < 0 and v1.co.y < 0 and min_z + H * 0.02 < m.z < min_z + H * 0.48: e.seam = True
bmesh.update_edit_mesh(mesh.data)

# 2. ZEN UV auto_uv_unwrap
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.zenuv_auto_uv_unwrap(auto_detect_hard_edges=False, use_normal=False, use_texel_density=True, texel_density=10.0, TD_TextureSizeX=2048, TD_TextureSizeY=2048, mark_seam_edges=True, correct_self_intersecting=True, stretch=False, packing=True)
print('auto_uv_unwrap: done')

# 3. Merge 1-face islands
bpy.ops.uv.seams_from_islands()
bm2 = bmesh.from_edit_mesh(mesh.data); bm2.faces.ensure_lookup_table()
visited = set(); islands = []
for face in bm2.faces:
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
        islands.append(island)
merged = 0
for island in islands:
    if len(island) == 1:
        for e in island[0].edges:
            if e.seam: e.seam = False; merged += 1
bmesh.update_edit_mesh(mesh.data)
print(f'merged: {merged}')

# 4. CONFORMAL unwrap_inplace
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.zenuv_unwrap_inplace(urp_method='CONFORMAL', fill_holes=True, correct_aspect=True)
print('CONFORMAL: done')

# 5. average + 2% margin
bpy.ops.uv.average_islands_scale()
bpy.ops.object.mode_set(mode='OBJECT')
uv = mesh.data.uv_layers.active; l = len(mesh.data.loops)
f = [0.0] * l * 2; uv.uv.foreach_get('vector', f)
us = f[0::2]; vs = f[1::2]
min_u, max_u = min(us), max(us); min_v, max_v = min(vs), max(vs)
ru = max(max_u - min_u, 1e-6); rv = max(max_v - min_v, 1e-6)
m = 0.02; s = 0.96
for i in range(len(us)): f[i * 2] = m + (us[i] - min_u) / ru * s; f[i * 2 + 1] = m + (vs[i] - min_v) / rv * s
uv.uv.foreach_set('vector', f)
grid = set()
for u, v in zip(f[0::2], f[1::2]): grid.add((int(u * 32), int(v * 32)))
print(f'Util: {100 * len(grid) / 1024:.1f}%')

RD = os.path.dirname(bpy.data.filepath)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, '04_uv.blend'))
print('SAVED')