"""Test MINIMUM_STRETCH (ARAP) with MINIMAL seams (target 7 anatomical cuts).
Prior test showed 26K seams → 12K islands (still fragmented).
This test uses VERY tight tolerance to mark only ~50-200 seam edges.
"""
import bpy, bmesh, math, json, time

def find_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    for o in bpy.data.objects:
        if o.type == 'MESH':
            return o
    return None

def clear_seams(mesh):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

def count_islands(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    visited = set()
    islands = 0
    for f in bm.faces:
        if f.index in visited:
            continue
        stack = [f]
        while stack:
            cf = stack.pop()
            if cf.index in visited:
                continue
            visited.add(cf.index)
            for e in cf.edges:
                if not e.seam:
                    for lf in e.link_faces:
                        if lf.index not in visited:
                            stack.append(lf)
        islands += 1
    bm.free()
    return islands

def mark_minimal_seams(mesh):
    """Mark ONLY ~7 anatomical seams with EXTREMELY tight tolerance.
    Based on retopo-uv-fragmentation-fix.md guidance."""
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    H = max_z - min_z
    W = max_x - min_x
    D = max_y - min_y
    # EXTREMELY tight tolerances
    xt = W * 0.0015    # back center: 0.15% of width
    xt_leg = W * 0.002 # leg inner: 0.2% of width
    zt_arm = H * 0.005 # armpit: 0.5% of height
    zt_leg = H * 0.01  # leg band
    print(f"  bbox: W={W:.3f} D={D:.3f} H={H:.3f} mid_x={mid_x:.3f}")
    print(f"  tolerances: xt={xt:.4f} xt_leg={xt_leg:.4f} zt_arm={zt_arm:.4f} zt_leg={zt_leg:.4f}")

    seams = 0
    seam_types = {'back_center':0, 'armpit_L':0, 'armpit_R':0, 'leg_L':0, 'leg_R':0}
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2
        # 1. Back center line (Y>0=back)
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt \
           and v0.co.y > 0 and v1.co.y > 0 \
           and min_z + H*0.05 < m.z < min_z + H*0.95:
            e.seam = True; seams += 1; seam_types['back_center'] += 1; continue
        # 2. Left armpit (Z~0.76H, X<0, Y<0 front)
        if min_z + H*0.75 < m.z < min_z + H*0.77 \
           and v0.co.x < mid_x - W*0.15 and v1.co.x < mid_x - W*0.15 \
           and v0.co.y < 0 and v1.co.y < 0:
            e.seam = True; seams += 1; seam_types['armpit_L'] += 1; continue
        # 3. Right armpit
        if min_z + H*0.75 < m.z < min_z + H*0.77 \
           and v0.co.x > mid_x + W*0.15 and v1.co.x > mid_x + W*0.15 \
           and v0.co.y < 0 and v1.co.y < 0:
            e.seam = True; seams += 1; seam_types['armpit_R'] += 1; continue
        # 4. Left leg inner (Z~0.05-0.45H, near mid_x-0.02W, Y<0 front)
        if min_z + H*0.05 < m.z < min_z + H*0.45 \
           and abs(v0.co.x - (mid_x - W*0.015)) < xt_leg \
           and abs(v1.co.x - (mid_x - W*0.015)) < xt_leg \
           and v0.co.y < 0 and v1.co.y < 0:
            e.seam = True; seams += 1; seam_types['leg_L'] += 1; continue
        # 5. Right leg inner
        if min_z + H*0.05 < m.z < min_z + H*0.45 \
           and abs(v0.co.x - (mid_x + W*0.015)) < xt_leg \
           and abs(v1.co.x - (mid_x + W*0.015)) < xt_leg \
           and v0.co.y < 0 and v1.co.y < 0:
            e.seam = True; seams += 1; seam_types['leg_R'] += 1; continue
    bm.to_mesh(mesh.data)
    bm.free()
    print(f"  seam types: {seam_types}")
    return seams, seam_types

def run_minimal(method, iterations=20):
    mesh = find_mesh()
    if not mesh:
        return {'error': 'no mesh'}
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name='UVMap')
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]

    clear_seams(mesh)
    seams, seam_types = mark_minimal_seams(mesh)
    pre_islands = count_islands(mesh)
    print(f"  seams={seams} pre_unwrap_islands={pre_islands}")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    t0 = time.time()
    kwargs = dict(method=method, fill_holes=True, correct_aspect=True,
                  margin_method='SCALED', margin=0.003)
    if method == 'MINIMUM_STRETCH':
        kwargs['iterations'] = iterations
    bpy.ops.uv.unwrap(**kwargs)
    t1 = time.time()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True,
                            margin_method='SCALED', margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    t2 = time.time()

    return {
        'method': method, 'iterations': iterations if method=='MINIMUM_STRETCH' else None,
        'seams': seams, 'seam_types': seam_types,
        'pre_unwrap_islands': pre_islands,
        'unwrap_time_s': round(t1-t0,2), 'total_time_s': round(t2-t0,2),
    }

if __name__ == '__main__':
    mesh = find_mesh()
    print(f"Mesh: {mesh.name if mesh else 'NONE'} | verts={len(mesh.data.vertices) if mesh else 0} faces={len(mesh.data.polygons) if mesh else 0}")
    results = []
    for method in ['MINIMUM_STRETCH', 'CONFORMAL']:
        print(f"\n--- Testing {method} with minimal seams ---")
        try:
            r = run_minimal(method, iterations=20)
            print(f"  RESULT: {r}")
            results.append(r)
        except Exception as e:
            import traceback
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results.append({'method': method, 'error': str(e)})
    print("\n=== RESULTS JSON ===")
    print(json.dumps(results, indent=2, default=str))
    print("=== DONE ===")

