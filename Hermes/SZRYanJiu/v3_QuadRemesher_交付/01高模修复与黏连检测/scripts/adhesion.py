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


def _model_height(obj):
    """模型身高(站直接地后bbox的z向尺寸), 用于按比例推导阈值"""
    import mathutils
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    zs = [c.z for c in corners]
    return max(zs) - min(zs)


def _exclusion_limits(height):
    """四肢末端排除区阈值, 按身高比例推导(不写死绝对坐标)。

    参考比例(成人身高1.8m实测):
      手腕以远 |X| > 身高 * WRIST_X_RATIO (0.42/1.8 = 0.233)
      脚踝以下  Z  < 身高 * ANKLE_Z_RATIO (0.10/1.8 = 0.056)
    这些区域AI生成质量差(融合手/薄片脚), 黏连推开会产生碎片。
    跨体型(孩童/女人/老人)按身高线性缩放, 保持相对部位一致。
    """
    WRIST_X_RATIO = 0.42 / 1.8   # 手腕|X| / 身高
    ANKLE_Z_RATIO = 0.10 / 1.8   # 脚踝Z / 身高
    return height * WRIST_X_RATIO, height * ANKLE_Z_RATIO


def _in_exclusion_zone(c, wrist_x, ankle_z):
    """四肢末端排除区: 手腕以远(|X|>wrist_x) + 脚踝以下(Z<ankle_z)"""
    return abs(c.x) > wrist_x or c.z < ankle_z


def detect_adhesion(obj, threshold_mm=None, max_pairs=2000):
    """Detect true adhesion pairs: close, facing each other, non-adjacent,
    NOT in limb-extremity exclusion zones.

    Stricter than proximity-only: requires n·dir > 0.5 (nearly opposing normals)
    to filter out clothing-on-body and normal close surface pairs.
    Exclusion zones按身高比例计算(见_exclusion_limits)。

    threshold_mm: 黏连判定距离。None=按身高自动(身高mm/360, 成人1.8m→5mm)。
    """
    mesh = obj.data
    # 黏连判定距离按身高比例(成人1.8m→5mm, 孩童1.1m→3mm), 不写死
    if threshold_mm is None:
        threshold_mm = _model_height(obj) * 1000 / 360.0
    threshold = threshold_mm / 1000.0
    n_faces = len(mesh.polygons)
    print(f"  Detecting: {n_faces} faces, threshold={threshold_mm:.2f}mm (按身高自动)")

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    # 排除区阈值按模型身高比例推导(不写死绝对坐标)
    height = _model_height(obj)
    wrist_x, ankle_z = _exclusion_limits(height)
    print(f"  模型身高{height:.3f}m → 排除区: 手腕|X|>{wrist_x:.3f} 脚踝Z<{ankle_z:.3f}")

    centers = []
    normals = []
    excluded = []  # 预计算排除标记
    for f in bm.faces:
        c = f.calc_center_median()
        centers.append(c)
        normals.append(f.normal.normalized())
        excluded.append(_in_exclusion_zone(c, wrist_x, ankle_z))

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

    # 推开前: 保存受影响面的原始法线
    face_normals_before = {}
    for (fi, fj, dist) in adhesion_pairs:
        if fi not in face_normals_before:
            face_normals_before[fi] = bm.faces[fi].normal.normalized().copy()
        if fj not in face_normals_before:
            face_normals_before[fj] = bm.faces[fj].normal.normalized().copy()

    # 应用位移+clamp, 同时记录每个面的总位移
    clamped = 0
    face_displacement = {}  # fi -> 总位移向量
    for vi, push_vec in affected.items():
        if push_vec.length > max_displacement:
            push_vec = push_vec.normalized() * max_displacement
            clamped += 1
        bm.verts[vi].co += push_vec
    
    # 计算每个受影响面的平均位移
    for (fi, fj, dist) in adhesion_pairs:
        for f in [fi, fj]:
            if f not in face_displacement:
                face_displacement[f] = Vector((0, 0, 0))
            # 面的位移 = 其所有顶点位移的平均
            verts = [v for v in bm.faces[f].verts]
            disp = sum((affected[v.index] for v in verts if v.index in affected), Vector((0,0,0)))
            count = sum(1 for v in verts if v.index in affected)
            if count > 0:
                face_displacement[f] = disp / count

    if clamped:
        print(f"  Clamped {clamped} vertices to max_displacement={max_displacement*1000:.2f}mm")

    bm.to_mesh(mesh)
    bm.free()

    # 推开后: 根据位移方向修正法线
    # 如果面被推开了, 新法线应该与位移方向一致 (朝外)
    print("  Correcting normals by displacement direction...")
    bm2 = bmesh.new()
    bm2.from_mesh(mesh)
    bm2.faces.ensure_lookup_table()
    corrected = 0
    for fi, disp in face_displacement.items():
        if fi < len(bm2.faces) and disp.length > 0.0001:
            f = bm2.faces[fi]
            curr_n = f.normal.normalized()
            disp_dir = disp.normalized()
            # 如果当前法线与位移方向相反, 翻转
            # 位移方向 = 推开方向 = 应该朝外
            if curr_n.dot(disp_dir) < 0:
                f.normal_flip()
                corrected += 1
    bm2.to_mesh(mesh)
    bm2.free()
    mesh.update()
    print(f"  Corrected {corrected} face normals")
    
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


def adhesion_pipeline(obj, threshold_mm=None, push_step_mm=None,
                      smooth_iter=3, smooth_factor=0.15, max_pairs=2000):
    """Full adhesion detect + fix + verify.
    threshold_mm/push_step_mm: None=按身高自动(threshold=身高mm/360, push_step=threshold/10)"""
    stats = {}
    # 参数化: 判定距离按身高, 推开步长=判定距离的1/10(联动)
    if threshold_mm is None:
        threshold_mm = _model_height(obj) * 1000 / 360.0
    if push_step_mm is None:
        push_step_mm = threshold_mm / 10.0
    print(f"\n{'='*60}")
    print(f"ADHESION START: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")
    print(f"  threshold={threshold_mm:.2f}mm push_step={push_step_mm:.2f}mm (按身高自动)")

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
    parser.add_argument('--threshold', type=float, default=None, help='黏连判定距离mm, 默认按身高自动(身高mm/360)')
    parser.add_argument('--push_step', type=float, default=None, help='推开步长mm, 默认threshold/10')
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
