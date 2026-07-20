"""Test MINIMUM_STRETCH (ARAP) unwrap on 90K-face QR mesh.
This method is NEW in Blender 5.1 and was never tested in prior runs.
Goal: compare ANGLE_BASED vs CONFORMAL vs MINIMUM_STRETCH with anatomical seams.
"""
import bpy, bmesh, math, sys, os, json, time

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

def mark_anatomical_seams(mesh):
    """Mark 7 anatomical seams with tight tolerance (per retopo-uv-fragmentation-fix.md)."""
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
    xt = W * 0.005   # tight X tolerance
    zt = H * 0.04    # Z band tolerance

    seams = 0
    for e in bm.edges:
        v0, v1 = e.verts
        m = (v0.co + v1.co) / 2
        # 1. Back center line (Y>0 = back)
        if abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt \
           and v0.co.y > 0 and v1.co.y > 0 \
           and min_z + H*0.05 < m.z < min_z + H*0.95:
            e.seam = True; seams += 1; continue
        # 2-3. Armpits (Z ~ 0.76H)
        if min_z + H*0.72 < m.z < min_z + H*0.80 \
           and (v0.co.x < mid_x - W*0.12 or v0.co.x > mid_x + W*0.12):
            e.seam = True; seams += 1; continue
        # 4-5. Leg inner (Z ~ 0.05-0.45H, near mid_x)
        if min_z + H*0.05 < m.z < min_z + H*0.45 \
           and abs(v0.co.x - mid_x) < xt and abs(v1.co.x - mid_x) < xt \
           and v0.co.y < 0 and v1.co.y < 0:
            e.seam = True; seams += 1; continue
    bm.to_mesh(mesh.data)
    bm.free()
    return seams

def count_islands(mesh):
    """Flood-fill count UV islands based on seam edges."""
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

def uv_bounds_and_area(mesh):
    """Compute UV bbox and total area (proxy for texel density uniformity)."""
    uv = mesh.data.uv_layers.active
    if not uv:
        return None
    l = len(mesh.data.loops)
    f = [0.0] * l * 2
    uv.uv.foreach_get('vector', f)
    us = f[0::2]; vs = f[1::2]
    umin, umax = min(us), max(us)
    vmin, vmax = min(vs), max(vs)
    # approximate total uv area (sum of per-face triangle areas)
    return {
        'u_range': [round(umin,3), round(umax,3)],
        'v_range': [round(vmin,3), round(vmax,3)],
        'u_span': round(umax-umin, 3),
        'v_span': round(vmax-vmin, 3),
    }

def run_unwrap(method, iterations=10, use_avg_scale=True, use_pack=True):
    """Run unwrap with given method + optional post-processing."""
    mesh = find_mesh()
    if not mesh:
        return {'error': 'no mesh'}
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name='UVMap')
    # reset UV layer
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]

    clear_seams(mesh)
    seams = mark_anatomical_seams(mesh)
    pre_islands = count_islands(mesh)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    t0 = time.time()
    if method == 'SMART':
        bpy.ops.uv.smart_project(angle_limit=math.radians(66),
                                  island_margin=0.003, correct_aspect=True)
    else:
        kwargs = dict(method=method, fill_holes=True, correct_aspect=True,
                      margin_method='SCALED', margin=0.003)
        if method == 'MINIMUM_STRETCH':
            kwargs['iterations'] = iterations
        bpy.ops.uv.unwrap(**kwargs)
    t1 = time.time()
    if use_avg_scale:
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.average_islands_scale()
    if use_pack:
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(rotate=True, scale=True,
                                margin_method='SCALED', margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    t2 = time.time()

    bounds = uv_bounds_and_area(mesh)
    return {
        'method': method,
        'iterations': iterations if method == 'MINIMUM_STRETCH' else None,
        'seams_marked': seams,
        'pre_unwrap_islands': pre_islands,
        'unwrap_time_s': round(t1-t0, 2),
        'total_time_s': round(t2-t0, 2),
        'uv_bounds': bounds,
        'use_avg_scale': use_avg_scale,
        'use_pack': use_pack,
    }

if __name__ == '__main__':
    mesh = find_mesh()
    print(f"Mesh: {mesh.name if mesh else 'NONE'} | verts={len(mesh.data.vertices) if mesh else 0} faces={len(mesh.data.polygons) if mesh else 0}")
    results = []
    # Test 1: MINIMUM_STRETCH (ARAP) — NEW in 5.1, never tested before
    for method in ['ANGLE_BASED', 'CONFORMAL', 'MINIMUM_STRETCH']:
        try:
            r = run_unwrap(method, iterations=20)
            print(f"[{method}] seams={r['seams_marked']} pre_islands={r['pre_unwrap_islands']} time={r['total_time_s']}s bounds={r['uv_bounds']}")
            results.append(r)
        except Exception as e:
            import traceback
            print(f"[{method}] FAILED: {e}")
            traceback.print_exc()
            results.append({'method': method, 'error': str(e)})
    print("=== RESULTS JSON ===")
    print(json.dumps(results, indent=2))
    # Save the last result (MINIMUM_STRETCH) to a new UV layer for visual inspection
    print("=== DONE ===")

