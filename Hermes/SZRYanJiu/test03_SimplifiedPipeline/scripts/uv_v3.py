"""UV unwrap v3: Cylinder projection — topology-independent.
Projects body onto cylinder (Y axis), arms onto cylinder (Z axis).
Creates ~6-10 islands regardless of mesh complexity.
Works for any T-pose body type.
"""
import bpy, bmesh, random, math
from mathutils import Vector

def run():
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    # Clear all seams and ensure UV layer exists
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)

    # Analyze mesh
    verts = mesh.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    H = max_z - min_z
    W = max_x - min_x

    # Determine body regions by vertex selection
    # Body: |X| < W*0.12 (torso + head + legs)
    # Arms: |X| > W*0.12 (left and right arms)
    body_threshold = W * 0.12

    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(mesh.data)
    bm.verts.ensure_lookup_table()

    body_verts = set()
    arm_l_verts = set()
    arm_r_verts = set()

    for v in bm.verts:
        if abs(v.co.x - mid_x) < body_threshold:
            body_verts.add(v.index)
            v.select = True
        elif v.co.x < mid_x - body_threshold:
            arm_l_verts.add(v.index)
        else:
            arm_r_verts.add(v.index)

    # === BODY: Cylinder project (Y axis) ===
    bmesh.update_edit_mesh(mesh.data)
    bpy.ops.uv.cylinder_project(direction='ALIGN_TO_OBJECT',
                                 correct_aspect=True)
    bpy.ops.mesh.select_all(action='DESELECT')

    # === ARMS: Cylinder project (Z axis for horizontal arms) ===
    # Left arm
    for v in bm.verts:
        v.select = v.index in arm_l_verts
    bmesh.update_edit_mesh(mesh.data)
    bpy.ops.uv.cylinder_project(direction='ALIGN_TO_OBJECT',
                                 correct_aspect=True)

    # Right arm
    bpy.ops.mesh.select_all(action='DESELECT')
    for v in bm.verts:
        v.select = v.index in arm_r_verts
    bmesh.update_edit_mesh(mesh.data)
    bpy.ops.uv.cylinder_project(direction='ALIGN_TO_OBJECT',
                                 correct_aspect=True)

    # Normalize UVs to [0,1] range manually (no pack_islands needed)
    bpy.ops.object.mode_set(mode='OBJECT')
    uv_layer = mesh.data.uv_layers.active
    l = len(mesh.data.loops)
    f = [0.0] * l * 2
    uv_layer.uv.foreach_get('vector', f)
    us = f[0::2]; vs = f[1::2]
    if us and vs:
        min_u, max_u = min(us), max(us)
        min_v, max_v = min(vs), max(vs)
        range_u = max(max_u - min_u, 1e-6)
        range_v = max(max_v - min_v, 1e-6)
        for i in range(len(us)):
            f[i*2] = (us[i] - min_u) / range_u
            f[i*2+1] = (vs[i] - min_v) / range_v
        uv_layer.uv.foreach_set('vector', f)

    # Stats
    uv = mesh.data.uv_layers.active
    l = len(mesh.data.loops)
    f = [0.0] * l * 2
    uv.uv.foreach_get('vector', f)
    us = f[0::2]; vs = f[1::2]
    s = random.sample(list(zip(us, vs)), min(2000, l))
    islands = len(set((round(u, 3), round(v, 3)) for u, v in s))
    print(f'UV: islands~{islands} U[{min(us):.3f},{max(us):.3f}] V[{min(vs):.3f},{max(vs):.3f}]')
    return {'islands': islands}


if __name__ == '__main__':
    run()
