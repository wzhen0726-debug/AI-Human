"""UV unwrap v5: Smart UV 66° + manual arm/leg seams.
1. Mark seams on arm/leg inner (longitudinal cuts)
2. Smart UV Project 66° (Blender default — good balance)
3. No merge, no normalize — Smart UV packs correctly
"""
import bpy, bmesh, random, math

def run():
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name='UVMap')

    # Clear all seams
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Mark longitudinal seams for arms and legs
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    xs = [v.co.x for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    H = max_z - min_z
    W = max_x - min_x
    xt = W * 0.005

    seams = 0
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2

        # Back center (for body split)
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y > 0 and v1.co.y > 0 and \
           min_z + H * 0.05 < m.z < min_z + H * 0.95:
            e.seam = True; seams += 1; continue

        # Left arm inner (full length, Y < 0 = front/inner)
        if v0.co.x < mid_x - W * 0.12 and v1.co.x < mid_x - W * 0.12 and \
           v0.co.y < 0 and v1.co.y < 0 and \
           min_z + H * 0.65 < m.z < min_z + H * 0.85:
            # Check if edge is roughly along X (arm direction)
            dx = abs(v0.co.x - v1.co.x)
            dy = abs(v0.co.y - v1.co.y)
            if dx > dy * 0.5:
                e.seam = True; seams += 1; continue

        # Right arm inner
        if v0.co.x > mid_x + W * 0.12 and v1.co.x > mid_x + W * 0.12 and \
           v0.co.y < 0 and v1.co.y < 0 and \
           min_z + H * 0.65 < m.z < min_z + H * 0.85:
            dx = abs(v0.co.x - v1.co.x)
            dy = abs(v0.co.y - v1.co.y)
            if dx > dy * 0.5:
                e.seam = True; seams += 1; continue

        # Left leg inner
        if abs(v0.co.x - (mid_x - W * 0.015)) < xt and \
           abs(v1.co.x - (mid_x - W * 0.015)) < xt and \
           v0.co.y < 0 and v1.co.y < 0 and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue

        # Right leg inner
        if abs(v0.co.x - (mid_x + W * 0.015)) < xt and \
           abs(v1.co.x - (mid_x + W * 0.015)) < xt and \
           v0.co.y < 0 and v1.co.y < 0 and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue

    bm.to_mesh(mesh.data)
    bm.free()

    # Smart UV Project 66° (default — proven to work)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),
                              island_margin=0.003,
                              area_weight=0.0,
                              correct_aspect=True,
                              scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Stats
    uv = mesh.data.uv_layers.active
    l = len(mesh.data.loops)
    f = [0.0] * l * 2
    uv.uv.foreach_get('vector', f)
    us = f[0::2]; vs = f[1::2]
    s = random.sample(list(zip(us, vs)), min(2000, l))
    islands = len(set((round(u, 3), round(v, 3)) for u, v in s))
    print(f'UV: seams={seams} islands~{islands} U[{min(us):.3f},{max(us):.3f}] V[{min(vs):.3f},{max(vs):.3f}]')
    return {'seams': seams, 'islands': islands}


if __name__ == '__main__':
    run()
