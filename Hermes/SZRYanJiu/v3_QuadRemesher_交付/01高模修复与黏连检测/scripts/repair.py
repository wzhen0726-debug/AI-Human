"""
Stage 1: 高模几何修复 v3 — High-poly geometry repair (no voxel remesh).
Preserves original high face count and facial detail.
Output goes directly to adhesion stage, then final_weld_for_qr, then Quad Remesher.

v3 关键算法 (2026-07-31 视觉验证通过):
  - foot_score 判据区分身高轴 vs 臂展轴 (T-pose 臂展≈身高, 不能用"最大维度=身高")
  - _detect_face_direction 鼻部突出度检测面朝向, 统一转到面朝 -Y
  - final_weld_for_qr() 输出前强制焊接, 保证 QR-ready (解决 xremesh 卡 21%)

Steps:
  1. Import GLB, cleanup junk objects
  2. 清除预旋转 (混元 X-90°) → foot_score 朝向检测 → 站起 → 面朝向 -Y
  3. Center on origin (X=0, Y=0), ground at Z=0
  4. Remove doubles (0.05mm, 只合并真正重合顶点)
  5. Dissolve degenerate + 浮动碎面清理 (<0.01mm²)
  6. Fill holes (close all boundary edge loops)
  7. Fix non-manifold edges
  8. Laplacian smooth (渐进 0.30→0.10) + Taubin (λ=0.5/μ=-0.53, 保体积)
  9. Final fill holes + remove doubles
  10. Re-ground + Quality verification

Blender 5.1 background script.
"""
import bpy, bmesh, sys, os, json, argparse, math, time
import numpy as np
from mathutils import Vector, Matrix


def get_main_mesh():
    """Get the largest mesh object, removing all junk."""
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    for obj, _ in meshes[1:]:
        bpy.data.objects.remove(obj, do_unlink=True)
    return meshes[0][0]


def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)), \
           (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))


def _get_coords(obj):
    """All vertex coords as numpy (N,3)."""
    n = len(obj.data.vertices)
    arr = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get('co', arr)
    return arr.reshape(-1, 3)


def _apply_coords(obj, arr):
    obj.data.vertices.foreach_set('co', arr.reshape(-1))
    obj.data.update()


def _clear_preexisting_rotation(obj):
    """清除 matrix_world 预旋转 (混元 GLB 自带 X-90°): 应用到顶点后重置 basis."""
    eul = obj.matrix_world.to_euler()
    if abs(eul.x) > 0.01 or abs(eul.y) > 0.01 or abs(eul.z) > 0.01:
        print(f"  Clearing pre-existing rotation: {eul}")
        rot = np.array(obj.matrix_world.to_3x3(), dtype=np.float64)
        arr = _get_coords(obj)
        arr = arr @ rot.T
        _apply_coords(obj, arr)
        obj.matrix_basis = Matrix.Identity(4)
        return True
    return False


def _foot_score_for_axis(coords, axis):
    """候选轴的 foot_score = (低端1%顶点横截面积 - 高端1%顶点横截面积) / 整体截面.

    横截面积 = 该端顶点在另外两轴上的分布范围乘积。
    身高轴: 脚端(脚+小腿)截面明显大于头端 → 正值且最大。
    臂展轴: 两端都是手, 截面相近 → 接近 0 或负值。
    """
    idx = np.argsort(coords[:, axis])
    n = max(1, len(idx) // 100)
    lo, hi = coords[idx[:n]], coords[idx[-n:]]
    others = [a for a in range(3) if a != axis]
    # np.ptp() 兼容 numpy 1.x/2.x (2.0 移除了 ndarray.ptp 方法)
    lo_area = np.ptp(lo[:, others[0]]) * np.ptp(lo[:, others[1]])
    hi_area = np.ptp(hi[:, others[0]]) * np.ptp(hi[:, others[1]])
    total = np.ptp(coords[:, others[0]]) * np.ptp(coords[:, others[1]])
    if total <= 1e-12:
        return 0.0, lo_area, hi_area
    return (lo_area - hi_area) / total, lo_area, hi_area


def _rotate_verts(obj, mode):
    """顶点级旋转. mode:
    'x+90'  绕X+90° (躺→站, y→z)     'y-90'  绕Y-90° (x→z)
    'flip'  绕X180° (上下颠倒)
    'z+90'  绕Z+90° (x,y)→(-y,x)     'z-90' 绕Z-90° (x,y)→(y,-x)
    'z180'  绕Z180° (x,y)→(-x,-y)
    """
    arr = _get_coords(obj)
    # 必须 copy: numpy 视图别名会导致元组赋值读到已被覆盖的列 (x+90/y-90/z+90)
    x, y, z = arr[:, 0].copy(), arr[:, 1].copy(), arr[:, 2].copy()
    if mode == 'x+90':      # y→z, z→-y
        arr[:, 1], arr[:, 2] = -z, y
    elif mode == 'y-90':    # x→z, z→-x
        arr[:, 0], arr[:, 2] = -z, x
    elif mode == 'flip':    # 绕X 180°
        arr[:, 1], arr[:, 2] = -y, -z
    elif mode == 'z+90':
        arr[:, 0], arr[:, 1] = -y, x
    elif mode == 'z-90':
        arr[:, 0], arr[:, 1] = y, -x
    elif mode == 'z180':
        arr[:, 0], arr[:, 1] = -x, -y
    _apply_coords(obj, arr)


def _detect_face_direction(obj):
    """鼻部突出度检测当前面朝向. 取头顶12%区域, 比较四方向突出度."""
    coords = _get_coords(obj)
    zmin, zmax = coords[:, 2].min(), coords[:, 2].max()
    head = coords[coords[:, 2] > zmin + 0.88 * (zmax - zmin)]
    if len(head) < 10:
        head = coords
    c = head.mean(axis=0)
    cand = {
        '+X': head[:, 0].max() - c[0], '-X': c[0] - head[:, 0].min(),
        '+Y': head[:, 1].max() - c[1], '-Y': c[1] - head[:, 1].min(),
    }
    d = max(cand, key=cand.get)
    print(f"  Face protrusion: " + ", ".join(f"{k}={v:.4f}" for k, v in cand.items()))
    return d


def _face_to_negY(obj):
    """把当前面朝向统一转到 -Y (direction 语义 = 当前朝向, 不是目标方向).
    +X→绕Z+90°, -X→绕Z-90°, +Y→绕Z180°, -Y→不动."""
    d = _detect_face_direction(obj)
    if d == '-Y':
        print("  Face already -Y, no turn")
        return
    mode = {'+X': 'z+90', '-X': 'z-90', '+Y': 'z180'}[d]
    print(f"  Face direction {d} -> -Y ({mode})")
    _rotate_verts(obj, mode)


def rotate_to_standard(obj):
    """v3 朝向标准化: foot_score 判据区分身高轴与臂展轴.

    关键教训 (难题9): T-pose 臂展(1.81m)≈身高(1.80m),
    "bbox最大维度=身高轴"判据失效 → 必须用两端横截面积差。
    实测参考: foot_scores x≈0.000, y≈-0.58, z≈+0.097 → 身高沿Z(已站立)。
    """
    _clear_preexisting_rotation(obj)
    coords = _get_coords(obj)

    print("  [foot_score] candidate axes:")
    scores = {}
    for axis in range(3):
        s, lo_a, hi_a = _foot_score_for_axis(coords, axis)
        scores[axis] = s
        print(f"    axis {'XYZ'[axis]}: score={s:+.4f} (lo_area={lo_a:.5f} hi_area={hi_a:.5f})")
    height_axis = max(scores, key=scores.get)
    print(f"  Height axis detected: {'XYZ'[height_axis]} (score={scores[height_axis]:+.4f})")

    # ---- 1) 站起: 把身高轴转到 Z ----
    if height_axis == 2:
        # 已站立; 检查脚是否在下端 (脚端面积大 → 低端是脚, 正常)
        _, lo_a, hi_a = _foot_score_for_axis(coords, 2)
        if lo_a < hi_a:
            print("  Model upside-down (head at low end) -> flip around X")
            _rotate_verts(obj, 'flip')
        else:
            print("  Already standing, feet at low end — no stand-up")
    elif height_axis == 0:
        # 身高沿X: 绕Y旋转使 X→Z (选择让脚端落到 -Z)
        _, lo_a, hi_a = _foot_score_for_axis(coords, 0)
        print(f"  Height along X, standing up (y-90), lo_area={lo_a:.5f} hi_area={hi_a:.5f}")
        _rotate_verts(obj, 'y-90')
        coords = _get_coords(obj)
        _, lo_a, hi_a = _foot_score_for_axis(coords, 2)
        if lo_a < hi_a:
            print("  Feet ended at top -> flip around X")
            _rotate_verts(obj, 'flip')
    else:
        # 躺姿 (身高沿Y): 绕X+90°站起, 再检查脚端
        _, lo_a, hi_a = _foot_score_for_axis(coords, 1)
        print(f"  Lying pose (height along Y), standing up (x+90)")
        _rotate_verts(obj, 'x+90')
        coords = _get_coords(obj)
        _, lo_a, hi_a = _foot_score_for_axis(coords, 2)
        if lo_a < hi_a:
            print("  Feet ended at top -> flip around X")
            _rotate_verts(obj, 'flip')

    # ---- 2) 面朝向 -Y ----
    _face_to_negY(obj)

    mn, mx, dims = get_bbox(obj)
    print(f"  Final dims: x={dims[0]:.3f} y={dims[1]:.3f} z={dims[2]:.3f}")
    return True


def center_model(obj):
    """Center on origin (X=0, Y=0), feet at Z=0."""
    mn, mx, dims = get_bbox(obj)
    cx = (mn[0] + mx[0]) / 2.0
    cy = (mn[1] + mx[1]) / 2.0
    cz_min = mn[2]
    arr = _get_coords(obj)
    arr[:, 0] -= cx; arr[:, 1] -= cy; arr[:, 2] -= cz_min
    _apply_coords(obj, arr)
    print(f"  Centered: offset=({cx:.4f}, {cy:.4f}, {cz_min:.4f})")


def dissolve_degenerate(obj):
    """Dissolve zero-area faces (merges into neighbors, no holes)."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    degen = [f for f in bm.faces if f.calc_area() < 1e-10]
    if degen:
        bmesh.ops.dissolve_faces(bm, faces=degen)
    loose = [v for v in bm.verts if len(v.link_edges) == 0]
    for v in loose:
        bm.verts.remove(v)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Dissolved: {len(degen)} degenerate, {len(loose)} loose verts")
    return len(degen), len(loose)


def dissolve_floating_faces(obj, max_area=1e-8):
    """难题11 (v19): 删除面积 <0.01mm² (1e-8 m²) 的孤立浮动碎面.

    只删孤立碎面 (所有邻接面同样极小), 避免误伤正常表面的小三角."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    tiny = [f for f in bm.faces if f.calc_area() < max_area]
    removed = 0
    for f in tiny:
        try:
            # BMFace 无 link_faces 属性: 邻接面 = 各边 link_faces 的并集(除自身)
            neighbors = set()
            for e in f.edges:
                neighbors.update(lf for lf in e.link_faces if lf != f)
            if not neighbors or all(nf.calc_area() < max_area * 10 for nf in neighbors):
                bm.faces.remove(f)
                removed += 1
        except (ValueError, ReferenceError):
            pass
    loose = [v for v in bm.verts if len(v.link_edges) == 0]
    for v in loose:
        bm.verts.remove(v)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Floating faces removed: {removed}, orphan verts: {len(loose)}")
    return removed


def fix_non_manifold_edges(obj):
    """Fix non-manifold edges by dissolving edges shared by >2 faces."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    over_connected = [e for e in bm.edges if len(e.link_faces) > 2]
    fixed = 0
    for e in over_connected:
        faces_to_remove = list(e.link_faces[2:])
        for f in faces_to_remove:
            try:
                bm.faces.remove(f)
                fixed += 1
            except (ValueError, ReferenceError):
                pass
    boundary_verts = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Fixed {fixed} non-manifold faces, {boundary_verts} boundary edges remain")
    return fixed


def laplacian_smooth(obj, iterations=2, lambda_factor=0.3):
    """渐进式 Laplacian smooth: 因子从 lambda_factor 线性衰减到 lambda_factor*0.33."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    for it in range(iterations):
        f = lambda_factor - (lambda_factor * 0.67) * (it / max(iterations - 1, 1))
        try:
            bpy.ops.mesh.vertices_smooth_laplacian(repeat=1, lambda_factor=f)
        except AttributeError:
            bpy.ops.mesh.vertices_smooth(factor=f, repeat=1)
    bpy.ops.object.mode_set(mode='OBJECT')


def taubin_smooth(obj, lam=0.5, mu=-0.53, iterations=1):
    """难题11 (v19): Taubin 平滑 λ=0.5/μ=-0.53, 保体积不缩模型, 消除局部突起.

    对每个顶点: v += λ*(邻域均值 - v), 再 v += μ*(邻域均值 - v)."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    for _ in range(iterations):
        for factor in (lam, mu):
            new_cos = []
            for v in bm.verts:
                nbs = [e.other_vert(v).co for e in v.link_edges]
                if nbs:
                    avg = Vector((0, 0, 0))
                    for c in nbs:
                        avg += c
                    avg /= len(nbs)
                    new_cos.append(v.co + factor * (avg - v.co))
                else:
                    new_cos.append(v.co.copy())
            for v, c in zip(bm.verts, new_cos):
                v.co = c
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Taubin smooth: lam={lam} mu={mu} iter={iterations}")


def verify_mesh(obj):
    mesh = obj.data
    bm = bmesh.new(); bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    loose = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    degen = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    mn, mx, dims = get_bbox(obj)
    oriented = dims[0] > dims[1] * 1.5
    bm.free()
    result = {
        "verts": len(mesh.vertices), "faces": len(mesh.polygons),
        "non_manifold_edges": non_manifold, "boundary_edges": boundary,
        "loose_verts": loose, "degenerate_faces": degen,
        "watertight": boundary == 0, "manifold": non_manifold == 0,
        "oriented_correctly": oriented,
        "dimensions": {"x": round(dims[0], 4), "y": round(dims[1], 4), "z": round(dims[2], 4)},
    }
    result["PASS"] = (loose == 0) and (degen <= 1) and (non_manifold < 50) and (boundary < 50) and oriented
    return result


def final_weld_for_qr(obj):
    """v17 新增 (难题7): 输出 blend 前强制焊接, 保证 QR-ready.

    根因: 172,285 未焊接重复顶点 + 516,960 开放边界边 → xremesh 卡 21%。
    1. remove_doubles(dist=0.0001)  2. edgeloop_fill 补孔 (上限30000防异常)
    3. 二次 remove_doubles          4. 验证 非流形<50 且 边界<50
    实测效果: 1,137,322→964,764 顶点, 边界 516,960→11, QR 90秒完成。
    """
    print("\n[final_weld_for_qr] QR-ready welding...")
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
    welded1 = before - len(bm.verts)

    filled = 0
    attempts = 0
    for e in list(bm.edges):
        if len(e.link_faces) == 1:
            attempts += 1
            if attempts > 30000:
                break
            try:
                res = bmesh.ops.edgeloop_fill(bm, edges=[e])
                filled += len(res.get("faces", []))
            except Exception:
                pass

    before2 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
    welded2 = before2 - len(bm.verts)

    bm.edges.ensure_lookup_table()
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bd = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    print(f"  Welded {welded1}+{welded2} verts, filled {filled} hole faces")
    print(f"  Post-weld: non_manifold={nm} boundary={bd} -> {'QR-READY' if nm < 50 and bd < 50 else 'WARNING'}")
    return {"welded": welded1 + welded2, "filled": filled, "non_manifold": nm, "boundary": bd}


def repair_pipeline(obj, smooth_iter=2, smooth_factor=0.3, weld_for_qr=True):
    """Main repair pipeline v3 — preserves high face count, no Voxel Remesh."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mesh = obj.data
    stats = {"initial_verts": len(mesh.vertices), "initial_faces": len(mesh.polygons)}
    print(f"\n{'='*60}")
    print(f"REPAIR START: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")

    print("\n[1] Orientation (foot_score v3)...")
    stats["rotated"] = rotate_to_standard(obj)

    print("\n[2] Center & ground...")
    center_model(obj)

    print("\n[3] Remove doubles (0.05mm)...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.00005)  # 0.05mm, 避免拉碎AI融合手
    bpy.ops.object.mode_set(mode='OBJECT')
    stats["after_remove_doubles"] = len(mesh.vertices)
    print(f"  {len(mesh.vertices)} verts")

    print("\n[4] Dissolve degenerate...")
    stats["degen_cleaned"] = dissolve_degenerate(obj)

    print("\n[4.5] Dissolve floating faces (v19)...")
    stats["floating_removed"] = dissolve_floating_faces(obj)

    print("\n[5] Fill holes...")
    t0 = time.time()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=0)
    # 不做 normals_make_consistent: 在193万面上会翻转正确面 (难题2/4)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"  Done ({time.time()-t0:.1f}s)")

    print("\n[6] Fix non-manifold edges...")
    stats["non_manifold_fixed"] = fix_non_manifold_edges(obj)

    print(f"\n[7] Laplacian smooth (iter={smooth_iter})...")
    laplacian_smooth(obj, smooth_iter, smooth_factor)

    print("\n[7.5] Taubin smooth (volume-preserving, v19)...")
    taubin_smooth(obj, lam=0.5, mu=-0.53, iterations=1)

    print("\n[8] Final fill holes + remove doubles...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.00005)
    bpy.ops.mesh.fill_holes(sides=0)
    # 不做 normals_make_consistent (难题2/4)
    bpy.ops.object.mode_set(mode='OBJECT')

    print("\n[9] Re-ground...")
    mn, mx, dims = get_bbox(obj)
    if abs(mn[2]) > 0.0005:
        arr = _get_coords(obj)
        arr[:, 2] -= mn[2]
        _apply_coords(obj, arr)
        print(f"  Re-grounded: Z={mn[2]:.6f}")

    print("\n[10] Verify...")
    stats["verify"] = verify_mesh(obj)
    v = stats["verify"]
    status = "PASS" if v["PASS"] else "FAIL"

    if weld_for_qr:
        print("\n[11] Final weld for QR...")
        stats["final_weld"] = final_weld_for_qr(obj)

    print(f"\n{'='*60}")
    print(f"REPAIR COMPLETE: {status}")
    print(f"  {v['verts']} verts, {v['faces']} faces")
    print(f"  watertight={v['watertight']} manifold={v['manifold']}")
    print(f"  non_manifold={v['non_manifold_edges']} boundary={v['boundary_edges']}")
    print(f"  dims={v['dimensions']}")
    print(f"{'='*60}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smooth_iter', type=int, default=2)
    parser.add_argument('--smooth_factor', type=float, default=0.3)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh"); sys.exit(1)
    result = repair_pipeline(obj, args.smooth_iter, args.smooth_factor)
    print("Result:", json.dumps(result, indent=2))
    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
