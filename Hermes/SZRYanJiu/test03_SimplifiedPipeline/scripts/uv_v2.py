"""UV unwrap v2: 5 anatomical seams + CONFORMAL unwrap.
Works for any T-pose/A-pose body type.
Seams: back_center + 2 arm_inner + 2 leg_inner
"""
import bpy, bmesh, random

def run():
    mesh = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name][0]
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    # Clear all seams
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Analyze mesh geometry
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    H = max_z - min_z
    W = max_x - min_x
    D = max_y - min_y
    
    # Determine front/back: face is on -Y side (avg head Y < 0)
    head_verts = [v for v in bm.verts if v.co.z > min_z + H * 0.85]
    avg_head_y = sum(v.co.y for v in head_verts) / len(head_verts) if head_verts else 0
    back_y = max_y  # +Y is back
    
    # Tolerances
    xt = W * 0.004   # center line X tolerance
    yt = D * 0.05    # Y tolerance for armpit
    
    seams = 0
    
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2
        
        # 1. Back center line: X≈mid, Y>0 (back), full body height
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y > mid_y and v1.co.y > mid_y and \
           min_z + H * 0.05 < m.z < min_z + H * 0.95:
            e.seam = True; seams += 1; continue
        
        # 2. Arm inner left: X near body edge (negative side), front side
        # Arm meets body at X ≈ -0.09, at shoulder height
        body_edge_l = mid_x - W * 0.09  # approx body half-width
        if abs(v0.co.x - body_edge_l) < xt and abs(v1.co.x - body_edge_l) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.70 < m.z < min_z + H * 0.82:
            e.seam = True; seams += 1; continue
        
        # 3. Arm inner right: X near body edge (positive side), front side
        body_edge_r = mid_x + W * 0.09
        if abs(v0.co.x - body_edge_r) < xt and abs(v1.co.x - body_edge_r) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.70 < m.z < min_z + H * 0.82:
            e.seam = True; seams += 1; continue
        
        # 4. Leg inner left: X near center (slightly left), lower body
        leg_inner_l = mid_x - W * 0.02
        if abs(v0.co.x - leg_inner_l) < xt and abs(v1.co.x - leg_inner_l) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue
        
        # 5. Leg inner right: X near center (slightly right), lower body
        leg_inner_r = mid_x + W * 0.02
        if abs(v0.co.x - leg_inner_r) < xt and abs(v1.co.x - leg_inner_r) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue

    bm.to_mesh(mesh.data)
    bm.free()
    
    # CONFORMAL unwrap (doesn't auto-cut on hard edges like ANGLE_BASED)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=True,
                       correct_aspect=True, margin=0.005)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, margin=0.005)
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
