"""
Minimal UV unwrap: 7 strategic seams only.
Back center + armpits + crotch + neck ring + waist ring.
"""
import bpy, bmesh

def run():
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.edges.ensure_lookup_table()

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    H = max_z - min_z

    xt = (max_x - min_x) * 0.003
    yt = (max_y - min_y) * 0.04
    seams = 0

    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2

        # Back center line (upper back only, Y > mid_y, Z between shoulder and hip)
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y > mid_y and v1.co.y > mid_y and \
           min_z + H * 0.25 < m.z < min_z + H * 0.82:
            e.seam = True
            seams += 1
            continue

        # Armpits: X near shoulder, Y near body side
        if abs(v0.co.y - mid_y) < yt and abs(v1.co.y - mid_y) < yt and \
           abs(abs(v0.co.x) - abs(v1.co.x)) < xt and \
           min_z + H * 0.72 < m.z < min_z + H * 0.82:
            e.seam = True
            seams += 1
            continue

        # Crotch: X near center, Y below body, Z hip area
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y < mid_y - yt and v1.co.y < mid_y - yt and \
           min_z + H * 0.38 < m.z < min_z + H * 0.52:
            e.seam = True
            seams += 1
            continue

        # Neck ring
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < mid_x * 0.15 and \
           min_z + H * 0.80 < m.z < min_z + H * 0.86:
            e.seam = True
            seams += 1
            continue

        # Waist ring
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < mid_x * 0.12 and \
           min_z + H * 0.48 < m.z < min_z + H * 0.58:
            e.seam = True
            seams += 1
            continue

    bm.to_mesh(mesh.data)
    bm.free()

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.003)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')

    print(f'UV seams: {seams}')
    return {'seams': seams}


if __name__ == '__main__':
    run()
