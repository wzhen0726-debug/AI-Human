"""UV unwrap v4: Seam-based unwrap with post-stitch.
1. Mark 5 anatomical seams (back + 2 arm + 2 leg)
2. ANGLE_BASED unwrap
3. Manual stitch via Python (merge adjacent islands)
4. Normalize to [0,1]
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

    # Analyze mesh
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

    # Determine body/arm threshold
    body_threshold = W * 0.12
    xt = W * 0.005

    seams = 0
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2

        # 1. Back center: X≈0, Y>0, full height
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt and \
           v0.co.y > mid_y and v1.co.y > mid_y and \
           min_z + H * 0.05 < m.z < min_z + H * 0.95:
            e.seam = True; seams += 1; continue

        # 2. Arm inner left: at body edge (X<0), front side, shoulder height
        edge_l = mid_x - W * 0.10
        if abs(v0.co.x - edge_l) < xt * 2 and abs(v1.co.x - edge_l) < xt * 2 and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.70 < m.z < min_z + H * 0.82:
            e.seam = True; seams += 1; continue

        # 3. Arm inner right
        edge_r = mid_x + W * 0.10
        if abs(v0.co.x - edge_r) < xt * 2 and abs(v1.co.x - edge_r) < xt * 2 and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.70 < m.z < min_z + H * 0.82:
            e.seam = True; seams += 1; continue

        # 4. Leg inner left
        leg_l = mid_x - W * 0.015
        if abs(v0.co.x - leg_l) < xt and abs(v1.co.x - leg_l) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue

        # 5. Leg inner right
        leg_r = mid_x + W * 0.015
        if abs(v0.co.x - leg_r) < xt and abs(v1.co.x - leg_r) < xt and \
           v0.co.y < mid_y and v1.co.y < mid_y and \
           min_z + H * 0.02 < m.z < min_z + H * 0.48:
            e.seam = True; seams += 1; continue

    bm.to_mesh(mesh.data)
    bm.free()

    # ANGLE_BASED unwrap
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True,
                       correct_aspect=True, margin=0.005)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Manual stitch: merge UV vertices that are at the same 3D position
    # but in different UV islands (within 0.002 UV distance)
    uv_layer = mesh.data.uv_layers.active
    l = len(mesh.data.loops)
    uv_data = [0.0] * l * 2
    uv_layer.uv.foreach_get('vector', uv_data)

    # Get loop vertex indices
    vi_data = [0] * l
    mesh.data.loops.foreach_get('vertex_index', vi_data)

    # Build vertex → list of (loop_index, u, v) mapping
    vert_uvs = {}
    for li in range(l):
        vi = vi_data[li]
        u = uv_data[li * 2]
        v = uv_data[li * 2 + 1]
        if vi not in vert_uvs:
            vert_uvs[vi] = []
        vert_uvs[vi].append((li, u, v))

    # For each vertex, if loops have very different UVs, average them
    # This effectively stitches islands at seam boundaries
    merged = 0
    for vi, loops in vert_uvs.items():
        if len(loops) < 2:
            continue
        # Group by UV proximity
        groups = []
        for li, u, v in loops:
            placed = False
            for g in groups:
                gu, gv = g[0][1], g[0][2]
                if abs(u - gu) < 0.01 and abs(v - gv) < 0.01:
                    g.append((li, u, v))
                    placed = True
                    break
            if not placed:
                groups.append([(li, u, v)])

        # If multiple groups, merge them (average UVs)
        if len(groups) > 1:
            avg_u = sum(l[1] for g in groups for l in g) / sum(len(g) for g in groups)
            avg_v = sum(l[2] for g in groups for l in g) / sum(len(g) for g in groups)
            for g in groups:
                for li, u, v in g:
                    uv_data[li * 2] = avg_u
                    uv_data[li * 2 + 1] = avg_v
                    merged += 1

    uv_layer.uv.foreach_set('vector', uv_data)

    # Normalize to [0,1]
    us = uv_data[0::2]; vs = uv_data[1::2]
    min_u, max_u = min(us), max(us)
    min_v, max_v = min(vs), max(vs)
    ru = max(max_u - min_u, 1e-6)
    rv = max(max_v - min_v, 1e-6)
    for i in range(len(us)):
        uv_data[i*2] = (us[i] - min_u) / ru
        uv_data[i*2+1] = (vs[i] - min_v) / rv
    uv_layer.uv.foreach_set('vector', uv_data)

    # Count islands
    s = random.sample(list(zip(uv_data[0::2], uv_data[1::2])), min(2000, l))
    islands = len(set((round(u, 3), round(v, 3)) for u, v in s))
    print(f'UV: seams={seams} merged={merged} islands~{islands} U[{min(uv_data[0::2]):.3f},{max(uv_data[0::2]):.3f}] V[{min(uv_data[1::2]):.3f},{max(uv_data[1::2]):.3f}]')
    return {'seams': seams, 'merged': merged, 'islands': islands}


if __name__ == '__main__':
    run()
