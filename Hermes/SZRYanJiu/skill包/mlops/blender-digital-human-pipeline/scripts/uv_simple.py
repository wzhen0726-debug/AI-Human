"""UV unwrap: single back-center seam + Angle-Based Unwrap.
Minimalist approach for Quad Remesher output — produces ~400 islands
on 90K-face meshes, avoiding the 3000+ island fragmentation of
multi-seam strategic approaches.

Run: blender --background model.blend --python uv_simple.py
"""
import bpy, bmesh, random

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
    xs = [v.co.x for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    H = max_z - min_z
    xt = (max_x - min_x) * 0.003  # tight X tolerance

    seams = 0
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y > 0 and v1.co.y > 0 and \
           min_z + H * 0.05 < m.z < min_z + H * 0.95:
            e.seam = True
            seams += 1

    bm.to_mesh(mesh.data)
    bm.free()

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True,
                       correct_aspect=True, margin=0.004)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')

    uv = mesh.data.uv_layers.active
    l = len(mesh.data.loops)
    f = [0.0] * l * 2
    uv.uv.foreach_get('vector', f)
    us = f[0::2]; vs = f[1::2]
    s = random.sample(list(zip(us, vs)), min(1000, l))
    islands = len(set((round(u, 2), round(v, 2)) for u, v in s))
    print(f"UV: seams={seams} islands≈{islands} U[{min(us):.3f},{max(us):.3f}] V[{min(vs):.3f},{max(vs):.3f}]")

if __name__ == '__main__':
    run()