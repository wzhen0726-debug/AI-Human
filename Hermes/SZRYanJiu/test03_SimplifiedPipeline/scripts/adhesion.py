"""
Stage 2: 黏连检测与修复 — Adhesion detection and repair.
Works on high-poly model (preserved from repair stage).

Detects true adhesion: face pairs that are close AND facing each other
AND in body regions likely to clamp (inner thighs, underarms, etc).

Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, math, argparse, time
from mathutils import Vector, kdtree


def get_main_mesh():
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    return meshes[0][0]


def _in_exclusion_zone(c):
    """四肢末端排除区: 手腕以远(|X|>0.42) + 脚踝以下(Z<0.10)
    这些区域AI生成质量差(融合手/薄片脚), 黏连推开会产生碎片"""
    return abs(c.x) > 0.42 or c.z < 0.10


def detect_adhesion(obj, threshold_mm=5.0, max_pairs=2000):
    """Detect true adhesion pairs: close, facing each other, non-adjacent,
    NOT in limb-extremity exclusion zones.

    Stricter than proximity-only: requires n·dir > 0.5 (nearly opposing normals)
    to filter out clothing-on-body and normal close surface pairs.
    Exclusion zones: hands (|X|>0.35) and feet (Z<0.15) — AI hand/foot
    geometry is unreliable, pushing creates blade artifacts.
    """
    mesh = obj.data
    threshold = threshold_mm / 1000.0
    n_faces = len(mesh.polygons)
    print(f"  Detecting: {n_faces} faces, threshold={threshold_mm}mm")

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    centers = []
    normals = []
    excluded = []  # 预计算排除标记
    for f in bm.faces:
        c = f.calc_center_median()
        centers.append(c)
        normals.append(f.normal.normalized())
        excluded.append(abs(c.x) > 0.42 or c.z < 0.10)

    t0 = time.time()
    # KDTree 只含 active_faces 的点 (排除区不进树)
    active_faces = [i for i in range(n_faces) if not excluded[i]]
    print(f"  Active faces (non-excluded): {len(active_faces)}/{n_faces}")
    kd = kdtree.KDTree(len(active_faces))
    for new_i, orig_i in enumerate(active_faces):
        kd.insert(centers[orig_i], new_i)
    kd.balance()
    print(f"  KDTree built ({time.time()-t0:.1f}s)")

    t0 = time.time()
    adhesion_pairs = []
    processed = set()

    # 循环上限: 最多扫描 active_faces 的前 30% 或 120秒
    # 快速复检模式(max_pairs<=1000): 只扫前10万面
    if max_pairs <= 1000:
        scan_limit = 100000
        time_limit = 30.0
    else:
        scan_limit = max(len(active_faces) // 3, 80000)
        time_limit = 120.0  # 秒

    for new_i, orig_i in enumerate(active_faces):
        if new_i >= scan_limit:
            print(f"    Scan limit reached ({scan_limit})")
            break
        if time.time() - t0 > time_limit:
            print(f"    Time limit reached ({time_limit}s)")
            break
        if new_i % 50000 == 0 and new_i > 0:
            print(f"    {new_i}/{len(active_faces)}, pairs={len(adhesion_pairs)}")

        c_i = centers[orig_i]

        for (co, new_j, dist) in kd.find_range(c_i, 2.0 * threshold):
            orig_j = active_faces[new_j]
            if orig_i >= orig_j:
                continue
            if (orig_i, orig_j) in processed:
                continue

            fi, fj = bm.faces[orig_i], bm.faces[orig_j]
            shared = set(v.index for v in fi.verts) & set(v.index for v in fj.verts)
            if shared:
                continue

            dir_vec = centers[orig_j] - c_i
            if dir_vec.length < 1e-8:
                continue
            dir_vec = dir_vec.normalized()
            n_i, n_j = normals[orig_i], normals[orig_j]
            dot_i = n_i.dot(dir_vec)
            dot_j = n_j.dot(-dir_vec)

            if dot_i > 0.5 and dot_j > 0.5 and dist < threshold:
                adhesion_pairs.append((orig_i, orig_j, dist))
                processed.add((orig_i, orig_j))

        if len(adhesion_pairs) >= max_pairs:
            print(f"    Max pairs ({max_pairs})")
            break

    bm.free()
    elapsed = time.time() - t0
    print(f"  Found {len(adhesion_pairs)} pairs ({elapsed:.1f}s)")
    return adhesion_pairs


def fix_adhesion(obj, adhesion_pairs, push_step_mm=0.3, smooth_iter=3,
                 smooth_factor=0.15):
    """Push clamped verts apart, then smooth. Small steps to avoid distortion.

    Uses DETECTION-time normals (not post-push normals) for direction,
    clamps displacement per vertex to prevent blade artifacts,
    and applies progressive smoothing (0.35→0.10) to preserve detail.
    """
    if not adhesion_pairs:
        return {"affected_vertices": 0, "adhesion_pairs": 0}

    mesh = obj.data
    push_step = push_step_mm / 1000.0
    max_displacement = push_step * 3.0  # clamp: 单点最大位移≤3×步长

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # 用检测时的法线(未变形)计算推开方向
    affected = {}
    for (fi, fj, dist) in adhesion_pairs:
        f_i, f_j = bm.faces[fi], bm.faces[fj]
        n_i = f_i.normal.normalized()
        n_j = f_j.normal.normalized()
        # 每个面的顶点沿该面法线推开
        for v in f_i.verts:
            if v.index not in affected:
                affected[v.index] = Vector((0, 0, 0))
            affected[v.index] += n_i * push_step
        for v in f_j.verts:
            if v.index not in affected:
                affected[v.index] = Vector((0, 0, 0))
            affected[v.index] += n_j * push_step

    # 应用位移+clamp
    clamped = 0
    for vi, push_vec in affected.items():
        if push_vec.length > max_displacement:
            push_vec = push_vec.normalized() * max_displacement
            clamped += 1
        bm.verts[vi].co += push_vec
    if clamped:
        print(f"  Clamped {clamped} vertices to max_displacement={max_displacement*1000:.2f}mm")

    bm.to_mesh(mesh)
    bm.free()

    # 渐进式平滑: 0.35→0.10, 保护推开后的几何
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    for vi in affected:
        if vi < len(mesh.vertices):
            mesh.vertices[vi].select = True

    bpy.ops.object.mode_set(mode='EDIT')
    total = smooth_iter
    for it in range(total):
        # 渐进: 0.35 → 0.10
        f = 0.35 - 0.25 * (it / max(total - 1, 1))
        bpy.ops.mesh.vertices_smooth(factor=f, repeat=1)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    return {"affected_vertices": len(affected),
            "adhesion_pairs": len(adhesion_pairs),
            "clamped_vertices": clamped}


def adhesion_pipeline(obj, threshold_mm=5.0, push_step_mm=0.3,
                      smooth_iter=3, smooth_factor=0.15, max_pairs=2000):
    """Full adhesion detect + fix + verify."""
    stats = {}
    print(f"\n{'='*60}")
    print(f"ADHESION START: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")

    pairs = detect_adhesion(obj, threshold_mm, max_pairs)
    stats["pairs_detected"] = len(pairs)

    if pairs:
        result = fix_adhesion(obj, pairs, push_step_mm, smooth_iter, smooth_factor)
        stats.update(result)
        print(f"  Fixed: {result}")

        # 快速复检: 只扫前10万面确认残余 (不做全量detect)
        print("  Quick recheck (first 100K active faces)...")
        remaining = detect_adhesion(obj, threshold_mm, max_pairs=1000)
        stats["pairs_remaining"] = len(remaining)
        print(f"  Remaining: {len(remaining)}")
    else:
        stats["affected_vertices"] = 0
        stats["pairs_remaining"] = 0
        print("  No adhesion detected")

    print(f"{'='*60}")
    print("ADHESION COMPLETE")
    print(f"{'='*60}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=5.0)
    parser.add_argument('--push_step', type=float, default=0.3)
    parser.add_argument('--smooth_iter', type=int, default=3)
    parser.add_argument('--smooth_factor', type=float, default=0.15)
    parser.add_argument('--max_pairs', type=int, default=2000)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh"); sys.exit(1)

    result = adhesion_pipeline(obj, args.threshold, args.push_step,
                               args.smooth_iter, args.smooth_factor,
                               args.max_pairs)
    print("Adhesion Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
