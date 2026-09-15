"""01_1眼窝制作 - 开孔与压凹

步骤:
1. 按虹膜中心+椭圆尺寸选中开口内面片, 删除成洞
2. 开口周围顶点沿"全局前向(-Y)"压凹, 平滑衰减, 最深10mm
3. 清理边界环, 重算法线
"""
import bpy
import bmesh
import math
import numpy as np
from mathutils import Vector
from eye_socket_config import *

# v43: 眼区面删除前的 (dx,dz,u,v) UV样本缓存, 供 make_eye_cup 把贴图眼睛/睫毛细节映射回碗面.
# 根因: 贴图里画了完整眼睛(睫毛+虹膜+瞳孔), 但 make_eye_socket 删掉这些面后, make_eye_cup 给碗面
# 分配均匀肤色avg_uv → 睫毛丢失、眼窝里是纯肉色. 修复=删面前捕获眼区UV, 重建碗后按XZ位置加权映射回.
_EYE_UV_SAMPLES = {}

def load_eyelid_contour(side, n_points=72, margin_x_mm=0.0, margin_z_mm=0.0, outer_extra_mm=0.0, inner_extra_mm=0.0):
    """读3DDFA眼睑轮廓(杏仁形), 返回(x,z)多边形顶点列表.
    加密到n_points点(样条插值) + 方向性扩展(margin_x水平/margin_z垂直) + 外眼角extra + 内眼角extra.
    2026-08-13 v18: 6点折线→24点+0.5mm margin.
    v19: margin 0.5→2.0mm (均匀径向).
    v22: 外眼角+4mm内眼角+1.5mm.
    2026-08-13 v23: margin改为方向性(margin_x=2mm水平, margin_z=1mm垂直).
    根因: 均匀径向扩展使z方向也扩了2mm, 轮廓高13.3mm上沿z=1.684触及眉毛下缘1.68+,
    flood-fill删了眉毛区390面→UV撕裂. 方向性后高≈11.5mm上沿z≈1.677不碰眉毛."""
    import json, math
    import numpy as np
    d = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
    rim = [r for r in d[side]["rim_3d"] if r is not None]
    # 投影到x-z平面
    pts = np.array([[r[0], r[2]] for r in rim], dtype=np.float64)
    M = len(pts)
    # 加密: 弧长等间距采样
    seg_len = [np.linalg.norm(pts[(i+1)%M]-pts[i]) for i in range(M)]
    total = sum(seg_len)
    out = []
    acc = 0.0; i = 0
    for k in range(n_points):
        target = total * k / n_points
        while acc + seg_len[i] < target and i < M:
            acc += seg_len[i]; i = (i+1) % M
        t = (target - acc) / seg_len[i] if seg_len[i] > 1e-12 else 0
        pt = pts[i] + (pts[(i+1)%M] - pts[i]) * t
        out.append(tuple(pt))
    poly = out
    # 方向性扩展: 水平方向点(外/内眼角)扩mx, 垂直方向点(上下睑)扩mz, 对角平滑过渡
    cx = sum(p[0] for p in poly)/n_points
    cz = sum(p[1] for p in poly)/n_points
    mx = margin_x_mm / 1000.0
    mz = margin_z_mm / 1000.0
    expanded = []
    for x,z in poly:
        dx = x - cx; dz = z - cz
        dist = math.sqrt(dx*dx + dz*dz)
        if dist > 1e-9:
            # 椭圆式: x' = x + (dx/dist)*mx, z' = z + (dz/dist)*mz
            expanded.append((x + dx/dist*mx, z + dz/dist*mz))
        else:
            expanded.append((x, z))
    # 外眼角额外扩展: |x|最大的点, 额外推outer_extra_mm
    # 内眼角额外扩展: |x|最小的点, 额外推inner_extra_mm
    outer_idx = max(range(n_points), key=lambda i: abs(expanded[i][0]))
    inner_idx = min(range(n_points), key=lambda i: abs(expanded[i][0]))
    outer_dir = 1 if expanded[outer_idx][0] > 0 else -1
    inner_dir = -outer_dir
    outer_extra = outer_extra_mm / 1000.0
    falloff = [0.33, 0.66, 1.0, 0.66, 0.33]
    for j, f in enumerate(falloff):
        idx = (outer_idx - 2 + j) % n_points
        x, z = expanded[idx]
        expanded[idx] = (x + outer_dir * outer_extra * f, z)
    inner_extra = inner_extra_mm / 1000.0
    for j, f in enumerate(falloff):
        idx = (inner_idx - 2 + j) % n_points
        x, z = expanded[idx]
        expanded[idx] = (x + inner_dir * inner_extra * f, z)
    return expanded

def resample_ring(ring_pts, n):
    """把有序闭环顶点重采样成n个等间距点(线性插值). 解决杏仁轮廓顶点分布不均(0.7~2.9mm)导致的星爆.
    ring_pts: [Vector/坐标] 有序环. 返回 [(x,y,z)] 等间距n点."""
    import numpy as np
    pts = [np.array([p.x, p.y, p.z]) if hasattr(p,'x') else np.array(p) for p in ring_pts]
    M = len(pts)
    # 累计弧长
    seg = [np.linalg.norm(pts[(i+1)%M]-pts[i]) for i in range(M)]
    total = sum(seg)
    if total < 1e-9: return pts[:n]
    # 等间距目标弧长
    out = []
    acc = 0.0; i = 0
    for k in range(n):
        target = total * k / n
        while acc + seg[i] < target and i < M:
            acc += seg[i]; i = (i+1) % M
        # 在边i上按剩余比例插值
        t = (target - acc) / seg[i] if seg[i] > 1e-12 else 0
        out.append(tuple(pts[i] + (pts[(i+1)%M]-pts[i]) * t))
    return out

def point_in_polygon(x, z, poly):
    """射线法判断点(x,z)是否在多边形poly内. poly=[(x,z),...]"""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]; xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside

def point_poly_dist(x, z, poly):
    """点到多边形折线(XZ, 米)的最近距离."""
    import math as _m
    best = 1e9
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        vx, vz = bx - ax, bz - az
        L2 = vx * vx + vz * vz + 1e-18
        t = ((x - ax) * vx + (z - az) * vz) / L2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        dx, dz = ax + t * vx - x, az + t * vz - z
        d = _m.sqrt(dx * dx + dz * dz)
        if d < best:
            best = d
    return best


def cut_hole_by_prism(obj, poly, center, side):
    """v62: 用"手描轮廓沿Y贯穿的封闭棱柱"对头部做 boolean EXACT DIFFERENCE, 切出眼洞.
    棱柱侧壁 = 过轮廓段的竖直平面 → 切出的洞边界 XZ 投影必然落在轮廓折线上
    (spike实测: 偏差中位0.0000mm/最大0.047mm, 边界222顶点; 旧洪泛方案中位0.09~0.15/最大0.90~1.00mm).
    棱柱必须前后都穿出眼区(前端在脸外, 后端在颅内) → 结果=带竖直洞壁+平底的封闭体; 调用方再删洞壁面留出洞口.
    """
    scn = bpy.context.scene
    mesh = obj.data
    if bpy.context.view_layer.objects.active is None or bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    y_f = center.y - PRISM_FRONT_MM / 1000.0
    y_b = center.y + PRISM_BACK_MM / 1000.0
    pts = [(float(p[0]), float(p[1])) for p in poly]
    n = len(pts)
    # ---- v67: 切割方向跟随局部表面法向(用户诊断: 沿Y垂切遇到"跟前视图近似平行"的面时交线会跳) ----
    # 做法: 轮廓每点从正前方沿+Y射线打到表面 → 命中点 q(其XZ与射线起点相同) + 该处法向 n →
    #   沿 n 前后扫出切割体。这样交线在 q 处与表面横向相交(良态), 且环必然过 q → XZ 轮廓仍=手描线。
    #   法向与Y轴夹角限制在 NORMAL_MAX_DEG 内(防扫出体自交)。
    fpt = [(x, y_f, z) for (x, z) in pts]
    bpt = [(x, y_b, z) for (x, z) in pts]
    if CUT_FOLLOW_NORMAL:
        import mathutils
        _vm = mesh.vertices
        _pm = mesh.polygons
        _bvh = mathutils.bvhtree.BVHTree.FromPolygons(
            [tuple(v.co) for v in _vm], [tuple(pp.vertices) for pp in _pm],
            all_triangles=False, epsilon=0.0)
        _ydir = Vector((0.0, 1.0, 0.0))
        _lim = math.radians(NORMAL_MAX_DEG)
        _hit_ok = 0
        _f, _b = [], []
        for (x, z) in pts:
            _o = Vector((x, y_f, z))
            _h = _bvh.ray_cast(_o, _ydir)
            if _h[0] is None:
                _f.append((x, y_f, z)); _b.append((x, y_b, z))
                continue
            _q = Vector(_h[0]); _d = Vector(_h[1])
            if _d.length < 1e-9:
                _d = _ydir
            _d = _d.normalized()
            _ang = _d.angle(_ydir)
            if _ang > _lim:
                _ax = _d.cross(_ydir)
                if _ax.length < 1e-9:
                    _ax = Vector((1.0, 0.0, 0.0))
                _d = mathutils.Matrix.Rotation(_ang - _lim, 3, _ax.normalized()) @ _d
                _d = _d.normalized()
            _hit_ok += 1
            _f.append(tuple(_q - _d * (PRISM_FRONT_MM / 1000.0)))
            _b.append(tuple(_q + _d * (PRISM_BACK_MM / 1000.0)))
        fpt, bpt = _f, _b
        print(f"cut_hole_by_prism {side}: 法向跟随切割 命中 {_hit_ok}/{n} 点, 法向限角 {NORMAL_MAX_DEG}°")
    verts = fpt + bpt
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))          # 侧壁
    faces.append(tuple(range(n - 1, -1, -1)))       # 前盖(法线朝前)
    faces.append(tuple(range(n, 2 * n)))            # 后盖
    pm = bpy.data.meshes.new("socket_prism")
    pm.from_pydata(verts, [], faces)
    pm.validate()
    # v63b根因修复: 手描轮廓点序在左右眼可能反向(R侧由L镜像而来) → 棱柱面法线朝向不一致,
    #   boolean 会切出"3面共边"的坏拓扑(实测R侧207条非流形边, L侧0). 不依赖点序: 直接重算外向法线.
    _pbm = bmesh.new()
    _pbm.from_mesh(pm)
    bmesh.ops.recalc_face_normals(_pbm, faces=_pbm.faces[:])
    _pbm.to_mesh(pm)
    _pbm.free()
    # v63: 用【独立材质】标记 boolean 新面(棱柱的所有面→该材质). boolean EXACT 会把棱柱面的材质
    #   传给新生成的面(wall+盖) → 之后按 material_index 精确删除, 不靠几何容差(容差判据实测漏47面).
    tmp_mat = bpy.data.materials.get("SOCKET_CUT_TMP") or bpy.data.materials.new("SOCKET_CUT_TMP")
    pm.materials.append(tmp_mat)
    for p in pm.polygons:
        p.material_index = 0
    _head_mats = [m.name if m else None for m in obj.data.materials]
    if tmp_mat.name not in _head_mats:
        obj.data.materials.append(tmp_mat)
    cut_slot = [m.name if m else None for m in obj.data.materials].index(tmp_mat.name)
    prism = bpy.data.objects.new("socket_prism", pm)
    scn.collection.objects.link(prism)
    mod = obj.modifiers.new("socket_cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = prism
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(prism, do_unlink=True)
    bpy.data.meshes.remove(pm, do_unlink=True)
    print(f"cut_hole_by_prism {side}: EXACT DIFFERENCE 完成 ({n}边形棱柱, y[{y_f*1000:.0f},{y_b*1000:.0f}]mm, 新面材质槽={cut_slot})")
    return cut_slot


def smooth_contour(poly, n=None, harm=None):
    """v64: 手描轮廓 → 光滑闭合曲线(等弧长重采样 + 闭合DFT低通).

    根因(实测 _diag_rim3d.py): 手描 72 点轮廓自身 turn mean5.2°/max65.7°, 还含 180° 退化尖点;
    boolean 切出的边界 XZ 投影严格=该轮廓 → 折角被 1:1 复制到 rim 环上, 换角度看就是"急转弯/折角".
    做法: 按弧长等距重采样成 n 点, 再做周期性 DFT, 只保留前 harm 次谐波(闭合曲线低通),
    整体形状不变(偏差亚毫米级), 折角被磨掉。
    """
    n = int(n or RIM_CONTOUR_RESAMPLE)
    harm = int(harm if harm is not None else RIM_CONTOUR_HARMONICS)
    P = np.asarray([[float(p[0]), float(p[1])] for p in poly], dtype=np.float64)
    Q = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 0:
        return [(float(a), float(b)) for a, b in P]
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    x = np.interp(t, s, Q[:, 0])
    z = np.interp(t, s, Q[:, 1])
    X = np.fft.rfft(x); Z = np.fft.rfft(z)
    keep = min(harm, len(X) - 1)
    X[keep + 1:] = 0.0; Z[keep + 1:] = 0.0
    x2 = np.fft.irfft(X, n); z2 = np.fft.irfft(Z, n)
    out = [(float(a), float(b)) for a, b in zip(x2, z2)]
    # 与原始轮廓的最大偏差(自检)
    _P = np.asarray(out)
    _d = []
    for p in P:
        _dd = np.linalg.norm(_P - p, axis=1).min()
        _d.append(_dd)
    return out, float(max(_d) * 1000.0)


def denoise_rim_band(obj, center, side, poly):
    """v64: 只对 rim 带内侧做加权 Laplacian 去噪 —— 从源头修"换角度看 rim 环不直".

    根因(实测 _diag_rim3d.py): rim 环就是网格边环, 直接继承扫描面的微噪声 ——
    环相对平滑曲线抖动 中位0.26mm / p90 0.55mm / max 0.95~1.12mm, 3D转角 max 58~90°,
    相邻点深度二阶差分 中位0.11mm / max 0.9~1.1mm。正视图(-Y)完全看不出来, 一旋转就是波浪/锯齿。
    做法: 只在"到轮廓折线XZ距离 < BAND 且 眼区正面"的顶点上平滑, 权重按距离平方衰减(带边缘不动),
    人脸整体形状不受影响(带外顶点一律不动)。
    """
    if not RIM_DENOISE:
        return
    center = Vector((float(center[0]), float(center[1]), float(center[2])))
    band = RIM_DENOISE_BAND_MM / 1000.0
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    w = {}
    for v in bm.verts:
        if v.co.y > center.y + Y_FRONT_M:                       # 只碰眼区正面, 不碰颅内/后脑
            continue
        dx, dz = v.co.x - center.x, v.co.z - center.z
        if dx * dx + dz * dz > EYE_AREA_R ** 2:
            continue
        d = point_poly_dist(v.co.x, v.co.z, poly)
        if d < band:
            w[v.index] = (1.0 - d / band) ** 2               # 距离衰减权重
    if not w:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"denoise_rim_band {side}: 带内无顶点, 跳过")
        return
    _before = {vi: bm.verts[vi].co.copy() for vi in w}
    nbr = {vi: [e.other_vert(bm.verts[vi]).index for e in bm.verts[vi].link_edges] for vi in w}
    lam = RIM_DENOISE_LAMBDA
    for _ in range(RIM_DENOISE_PASSES):
        upd = {}
        for vi, ww in w.items():
            nb = nbr[vi]
            if not nb:
                continue
            acc = Vector((0.0, 0.0, 0.0))
            for ni in nb:
                acc += bm.verts[ni].co
            acc /= len(nb)
            upd[vi] = bm.verts[vi].co.lerp(acc, lam * ww)
        for vi, co in upd.items():
            bm.verts[vi].co = co
    _maxd = max((bm.verts[vi].co - _before[vi]).length for vi in w) * 1000.0
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"denoise_rim_band {side}: 带内顶点 {len(w)} (band={RIM_DENOISE_BAND_MM}mm, "
          f"{RIM_DENOISE_PASSES}passes, λ={lam}), 表面最大位移 {_maxd:.3f}mm")


def apply_local_inset(poly, center, side, insets):
    """v64d: 轮廓【局部内收】—— 绕开表面陡面/褶(那里跟前视图近乎平行, 沿Y垂切会让环的y跳)。

    用户方案(2026-09-14): 环是沿Y(前视图)垂直切下去的, 高模上眼窝附近的面并不都垂直于前视图;
    跟前视图近乎平行的那几处, 交线会跳 → 环在那折。把轮廓在那些位置本地往里收 1mm 绕开它。
    insets: [(side, dx_mm, dz_mm, radius_mm, inset_mm)] —— dx/dz 相对该眼中心, 单位mm。
    只动半径内、按 (1-(d/r)^2) 平滑衰减, 所以轮廓依然光滑; 手描 json 一个字节都不改。
    """
    if not insets:
        return poly
    P = np.array([[float(p[0]), float(p[1])] for p in poly], dtype=np.float64)
    cx, cz = float(center[0]), float(center[2])
    out = P.copy()
    for (s, dxm, dzm, rm, im) in insets:
        if s != side:
            continue
        t = np.array([cx + dxm / 1000.0, cz + dzm / 1000.0])
        r = rm / 1000.0
        ins = im / 1000.0
        d = np.linalg.norm(P - t, axis=1)
        w = np.clip(1.0 - (d / r) ** 2, 0.0, None)
        if w.max() <= 0:
            continue
        v = np.stack([cx - P[:, 0], cz - P[:, 1]], axis=1)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        v = v / np.maximum(n, 1e-12)
        out = out + v * (ins * w)[:, None]
        _mv = float(np.linalg.norm(out - P, axis=1).max()) * 1000.0
        print(f"apply_local_inset {side}: 目标点({dxm:+.1f},{dzm:+.1f})mm 半径{rm}mm 内收{im}mm, "
              f"影响 {int((w > 0).sum())} 个轮廓点, 最大位移 {_mv:.3f}mm")
    return [(float(a), float(b)) for a, b in out]


def relax_surface_at_spikes(obj, center, side):
    """v64b: 环上大转角处的【局部表面】加权去噪(带位移上限).

    根因(实测 _diag_L_ring.py): L 环 7 个 >30° 顶点全部集中在"下睑靠外眼角"一处
    (相对眼中心 dx≈-6~-7.5mm, dz≈-6.4mm), 该处表面 2mm 内深度起伏 1.5mm;
    环到手描轮廓只差 0.02~0.05mm → 不是切偏, 是那片表面自己起伏, 环贴上去就只能跟着折。
    做法: 先找环上转角 > 阈值的顶点 → 取其周围 R 内的表面顶点 → 加权 Laplacian 平滑(权重按距离衰减),
    位移超过 CAP 就停止 → 只动那一小片, 其余顶点一律不动。
    """
    if not RIM_SPIKE_SURF:
        return
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    nadj = {}
    for v in bm.verts:
        if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
            continue
        nb = [e.other_vert(v) for e in v.link_edges if len(e.link_faces) == 1]
        if len(nb) == 2:
            nadj[v.index] = [n.index for n in nb]
    if not nadj:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"relax_surface_at_spikes {side}: 未找到环")
        return
    bad = []
    for vi, nb in nadj.items():
        a = bm.verts[nb[0]].co - bm.verts[vi].co
        b = bm.verts[nb[1]].co - bm.verts[vi].co
        if a.length < 1e-9 or b.length < 1e-9:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, -(a.dot(b)) / (a.length * b.length)))))
        if ang > RIM_SPIKE_RELAX_THRESH_DEG:
            bad.append(vi)
    if not bad:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"relax_surface_at_spikes {side}: 无 >{RIM_SPIKE_RELAX_THRESH_DEG}° 尖点, 跳过")
        return
    R = RIM_SPIKE_SURF_R_MM / 1000.0
    targets = [bm.verts[i].co.copy() for i in bad]
    w = {}
    for v in bm.verts:
        dmin = min((v.co - t).length for t in targets)
        if dmin < R:
            w[v.index] = (1.0 - dmin / R) ** 2
    if not w:
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    before = {vi: bm.verts[vi].co.copy() for vi in w}
    nbr = {vi: [e.other_vert(bm.verts[vi]).index for e in bm.verts[vi].link_edges] for vi in w}
    cap = RIM_SPIKE_SURF_CAP_MM / 1000.0
    lam = RIM_SPIKE_SURF_LAMBDA
    passes_done = 0
    for _ in range(RIM_SPIKE_SURF_PASSES):
        upd = {}
        for vi, ww in w.items():
            nb = nbr[vi]
            if not nb:
                continue
            acc = Vector((0.0, 0.0, 0.0))
            for ni in nb:
                acc += bm.verts[ni].co
            acc /= len(nb)
            upd[vi] = bm.verts[vi].co.lerp(acc, lam * ww)
        for vi, co in upd.items():
            bm.verts[vi].co = co
        _mv = max((bm.verts[vi].co - before[vi]).length for vi in w)
        passes_done += 1
        if _mv > cap:                     # 位移到上限即停
            passes_done -= 1
            break
    _mv = max((bm.verts[vi].co - before[vi]).length for vi in w) * 1000.0
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"relax_surface_at_spikes {side}: 坏点 {len(bad)} 个 → 局部平滑表面顶点 {len(w)} 个 "
          f"(R={RIM_SPIKE_SURF_R_MM}mm, {passes_done}passes), 最大位移 {_mv:.3f}mm (上限 {RIM_SPIKE_SURF_CAP_MM}mm)")


def relax_ring_spikes(obj, center, side):
    """v64: rim 环去刺 —— 焊接退化小边后仍有少数大转角顶点(实测 L 侧 135°/180° 尖点,
    来自 boolean 在轮廓折角处产生的近重合顶点/折回边)。只动这些顶点:
    沿环上相邻点做局部松弛(不用面法向, 只在环内), 其余顶点一律不动。
    """
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    # 环邻接(只认"边界边": link_faces==1)
    nadj = {}
    for v in bm.verts:
        if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
            continue
        nb = [e.other_vert(v) for e in v.link_edges if len(e.link_faces) == 1]
        if len(nb) == 2:
            nadj[v.index] = [n.index for n in nb]
    if not nadj:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"relax_ring_spikes {side}: 未找到环")
        return
    lam = RIM_SPIKE_RELAX_LAMBDA
    moved_total = set()
    for _ in range(RIM_SPIKE_RELAX_PASSES):
        bad = []
        for vi, nb in nadj.items():
            a = bm.verts[nb[0]].co - bm.verts[vi].co
            b = bm.verts[nb[1]].co - bm.verts[vi].co
            if a.length < 1e-9 or b.length < 1e-9:
                continue
            cosang = max(-1.0, min(1.0, -(a.dot(b)) / (a.length * b.length)))   # 转角(180°-张角)
            ang = math.degrees(math.acos(cosang))
            if ang > RIM_SPIKE_RELAX_THRESH_DEG:
                bad.append(vi)
        if not bad:
            break
        upd = {}
        for vi in bad:
            nb = nadj[vi]
            mid = (bm.verts[nb[0]].co + bm.verts[nb[1]].co) * 0.5
            upd[vi] = bm.verts[vi].co.lerp(mid, lam)
            moved_total.add(vi)
        for vi, co in upd.items():
            bm.verts[vi].co = co
    bmesh.update_edit_mesh(mesh)
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if moved_total:
        print(f"relax_ring_spikes {side}: 松弛尖点顶点 {len(moved_total)} 个 "
              f"(阈值 {RIM_SPIKE_RELAX_THRESH_DEG}°, {RIM_SPIKE_RELAX_PASSES}passes)")
    else:
        print(f"relax_ring_spikes {side}: 无 >{RIM_SPIKE_RELAX_THRESH_DEG}° 尖点")


# ===================== 按模型推导的尺度参数(程序化, 换头/换眼型自动适配) =====================
# 原则: 代码里不再出现"只对当前这个头成立"的绝对 mm 值; 一切由
#   ①头对象 bbox(前伸/后伸/深度)  ②该侧眼睛自身尺寸(3ddfa width_mm/height_mm)
#   ③眼区局部网格分辨率(中位边长)  推导而来。
CUR = {}


def derive_scale(obj, center, side, dl=None):
    """推导并写入本侧尺度参数(模块级, 供后面所有函数使用)。"""
    global EYE_AREA_R, Y_FRONT_M, Y_BACK_SPLIT, PRISM_FRONT_MM, PRISM_BACK_MM
    global RIM_SKIN_EDGE_M
    global RIM_BAND_W_MM, RIM_BAND_ARC_MM, RIM_BAND_FINE_MM, RIM_WELD_MM
    global RIM_CONTOUR_RESAMPLE, RIM_SPIKE_SURF_R_MM
    import numpy as _np
    me = obj.data
    nv = len(me.vertices)
    co = _np.empty(nv * 3, dtype=_np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    y_min, y_max = float(co[:, 1].min()), float(co[:, 1].max())
    x_min, x_max = float(co[:, 0].min()), float(co[:, 0].max())
    z_min, z_max = float(co[:, 2].min()), float(co[:, 2].max())
    depth = y_max - y_min
    # 眼睛自身尺寸: 优先 3ddfa width/height, 否则用轮廓点跨度
    w_m = h_m = None
    if dl and dl.get("width_mm"):
        w_m = float(dl["width_mm"]) / 1000.0
        h_m = float(dl.get("height_mm") or (w_m * 1000 * 0.35)) / 1000.0
    if w_m is None:
        try:
            rp = _np.array([[r[0], r[2]] for r in dl["rim_3d"] if r is not None], dtype=_np.float64)
            w_m = float(rp[:, 0].ptp()); h_m = float(rp[:, 1].ptp())
        except Exception:
            w_m, h_m = 0.035, 0.012
    eye_w = max(w_m, 1e-4)
    # ① 眼区判定半径(原硬编码 0.030): 0.86 × 眼宽
    EYE_AREA_R = 0.86 * eye_w
    # ② "眼中心之前"的 y 阈值(原硬编码 +0.010): 0.29 × 眼宽
    Y_FRONT_M = 0.29 * eye_w
    # ③ 后脑/前脸分界(原硬编码 -0.020): bbox 前 44% 处
    Y_BACK_SPLIT = y_min + 0.44 * depth
    # ④ 棱柱前后伸出量(原硬编码 80/45): 以眼中心为界 + 20% 头深余量
    PRISM_FRONT_MM = (center.y - y_min) * 1000.0 + 0.20 * depth * 1000.0
    # 后伸只到 rim 最深处 + 0.25×眼宽 —— 原来按 bbox 后极算, 棱柱贯穿整个头 →
    # 后脑勺被一起抠穿(用户实测)。眼窝只需要切前脸这一侧。
    try:
        _ry = [float(r[1]) for r in dl["rim_3d"] if r is not None]
        _rim_back = max(_ry)          # y 越大越靠后
    except Exception:
        _rim_back = center.y + 0.25 * eye_w
    PRISM_BACK_MM = (_rim_back - center.y) * 1000.0 + 0.25 * eye_w * 1000.0
    # ⑤ 眼区局部网格分辨率(中位边长, 用顶点在眼区内的边统计)
    ne = len(me.edges)
    ev = _np.empty(ne * 2, dtype=_np.int32)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(ne, 2)
    cx, cz = float(center[0]), float(center[2])
    # 只统计【rim 轮廓 3mm 内】的网格 —— 那才是 rim 重建真正要删/要细分的那圈,
    # 用整块 30mm 区域会把眉毛/脸颊的粗面算进来(实测中位被拉到 1.39mm → 带被放大 4 倍 → 越修越坏)
    try:
        _rp = _np.array([[r[0], r[2]] for r in dl["rim_3d"] if r is not None], dtype=_np.float64)
    except Exception:
        _rp = None
    if _rp is not None and len(_rp) > 5:
        _px = co[ev[:, 0], 0][:, None] - _rp[None, :, 0]
        _pz = co[ev[:, 0], 2][:, None] - _rp[None, :, 1]
        _dmin = _np.sqrt(_px ** 2 + _pz ** 2).min(axis=1)
        m = (_dmin < 0.003) & (co[ev[:, 0], 1] < center.y + 0.29 * eye_w)
    else:
        d2 = (co[ev[:, 0], 0] - cx) ** 2 + (co[ev[:, 0], 2] - cz) ** 2
        m = (d2 < (0.86 * eye_w) ** 2) & (co[ev[:, 0], 1] < center.y + 0.29 * eye_w)
    if int(m.sum()) >= 30:
        a = co[ev[m, 0]]; b = co[ev[m, 1]]
        med = float(_np.median(_np.linalg.norm(a - b, axis=1)))
    else:
        med = 0.0003
    med = max(med, 5e-5)
    RIM_SKIN_EDGE_M = med            # 模块级: 皮肤中位边长(米), 供 ⑦b 等使用
    # 带宽按【眼睛自身尺寸】定(0.035×眼宽 ≈ 1.2mm@35mm眼)
    RIM_BAND_W_MM = 0.035 * eye_w * 1000.0
    # 细分/边界阈值按【实测皮肤中位边长】推导 —— 让缝合带密度与周围皮肤一致,
    # 避免"带内过密 → 线框远看发黑"(用户实测) 且不长于邻面。
    _med_mm = med * 1000.0
    RIM_BAND_FINE_MM = max(0.6, 0.90 * _med_mm)
    RIM_BAND_ARC_MM = max(0.5, 1.40 * _med_mm)
    RIM_WELD_MM = 0.05 * RIM_BAND_W_MM
    RIM_SPIKE_SURF_R_MM = 2.5 * RIM_BAND_W_MM
    # ⑥ 轮廓重采样点数: 周长 / 0.35mm, 限 120~600
    try:
        rp3 = _np.array([[r[0], r[2]] for r in dl["rim_3d"] if r is not None], dtype=_np.float64)
        per = float(_np.linalg.norm(_np.roll(rp3, -1, axis=0) - rp3, axis=1).sum())
    except Exception:
        per = 0.084
    RIM_CONTOUR_RESAMPLE = int(min(600, max(120, round(per / 0.00035))))
    CUR.update(dict(side=side, eye_w=eye_w, eye_h=h_m, med_edge=med,
                    bbox=(x_min, x_max, y_min, y_max, z_min, z_max), depth=depth))
    print(f"derive_scale {side}: 眼宽{eye_w*1000:.2f}mm 头深{depth*1000:.1f}mm "
          f"| 眼区半径{EYE_AREA_R*1000:.2f}mm 前阈值{Y_FRONT_M*1000:.2f}mm 后分界{Y_BACK_SPLIT*1000:.1f}mm "
          f"| 棱柱前{PRISM_FRONT_MM:.0f}/后{PRISM_BACK_MM:.0f}mm | 局部中位边长{med*1000:.3f}mm "
          f"→ 带宽{RIM_BAND_W_MM:.2f} 弧长{RIM_BAND_ARC_MM:.2f} 细分{RIM_BAND_FINE_MM:.2f} 焊{RIM_WELD_MM:.3f}mm "
          f"| 轮廓重采样{RIM_CONTOUR_RESAMPLE}点")


def _seg_int_xz(a1, a2, b1, b2):
    """两条 XZ 线段求交(不含端点), 返回 (t,u) 或 None."""
    d1 = a2 - a1
    d2 = b2 - b1
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-14:
        return None
    t = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / den
    u = ((b1[0] - a1[0]) * d1[1] - (b1[1] - a1[1]) * d1[0]) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (t, u)
    return None


def rebuild_rim_band(obj, center, side, poly, W_mm=None, tol_mm=0.35):
    """v85(D2): 沿【整圈】rim 重建皮肤带 —— 一次解决 rim 全部缺陷(折返尖/锯齿/间距不均)。

    做法: ①删掉沿手描轮廓 W mm 宽的一圈皮肤面(洞被扩大到该带的外缘)
          ②该带外缘(此时是唯一的洞边界)细分到 ≤ARC_MM
          ③内圈 = 手描轮廓本身, 重采样到与外圈【同点数】
          ④按点对点条带三角化缝回 → rim 环严格等于手描轮廓, 且均匀无折返
    皮肤带之外的皮肤一个顶点不动。
    """
    if not RIM_BAND_ENABLE:
        return
    if W_mm is None:
        W_mm = RIM_BAND_W_MM
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    cy = cv.y
    mesh = obj.data
    bm_pre = bmesh.new()
    bm_pre.from_mesh(mesh)          # 删面之前的快照(供取原 rim 边界)
    CP = np.array([[float(p[0]), float(p[1])] for p in poly], dtype=np.float64)   # 手描/光滑轮廓 XZ(mm? 否: 米)
    NP = len(CP)
    # 轮廓每点深度: 取最近表面点(closest_point_on_mesh)。不能用沿 Y 的 ray_cast ——
    # 洞口范围内射线会穿透打到后脑, 判无效再插值就把 rim 深度抹平了(用户: "Y轴拉平, 眼眶变形")
    # 深度不自己采样: 沿用【原 rim 边界】在相同角度上的 y (它就在表面上, 是真值) ——
    # 自采样(ray_cast 会穿透 / closest_point 会取到深处内壁)都会改变 rim 的 3D 形态(用户: "变形")
    _ob = [e for e in bm_pre.edges if len(e.link_faces) == 1
           and (e.verts[0].co - cv).xz.length < EYE_AREA_R and e.verts[0].co.y < cy + Y_FRONT_M]
    _ovs = set()
    for e in _ob:
        _ovs.add(e.verts[0]); _ovs.add(e.verts[1])
    if _ovs:
        th = np.array([np.arctan2(v.co.z - cv.z, v.co.x - cv.x) for v in _ovs])
        yy = np.array([v.co.y for v in _ovs])
        o = np.argsort(th)
        th = th[o]; yy = yy[o]
        th = np.concatenate([th - 2 * np.pi, th, th + 2 * np.pi])
        yy = np.concatenate([yy, yy, yy])
        CY = np.interp(np.arctan2(np.array([p[1] for p in poly]) - cv.z,
                                  np.array([p[0] for p in poly]) - cv.x), th, yy)
        print(f"rebuild_rim_band {side}: 深度沿用原 rim 边界(角度插值), 原边界 {len(_ovs)} 点, "
              f"y范围[{CY.min()*1000:.1f},{CY.max()*1000:.1f}]mm")
    else:
        CY = np.full(len(poly), cy)
        print(f"rebuild_rim_band {side}: 未取到原 rim 边界 → 深度用眼中心 y 兜底")

    # ---- ① 删轮廓 W mm 内的皮肤面 ----
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    W = W_mm / 1000.0
    # ---- ⓪ 先把带区域里的大面细分(粗面区会让带边界离轮廓很远 → 缝回来的面被拉长, 用户看到"拉伸出去")
    for _sub in range(4):
        bm.edges.ensure_lookup_table()
        _se = []
        for f in bm.faces:
            c = f.calc_center_median()
            if c.y > cy + Y_FRONT_M or (c - cv).xz.length > EYE_AREA_R:
                continue
            if np.sqrt((CP[:, 0] - c.x) ** 2 + (CP[:, 1] - c.z) ** 2).min() > 3.5 * W:
                continue
            for e in f.edges:
                if (e.verts[0].co - e.verts[1].co).length > RIM_BAND_FINE_MM / 1000.0:
                    _se.append(e)
        if not _se:
            break
        bmesh.ops.subdivide_edges(bm, edges=list(set(_se)), cuts=1, use_grid_fill=False)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

    victims = []
    _CPs = CP  # 轮廓折线(米), 闭合
    _NCP = len(_CPs)
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y > cy + Y_FRONT_M:
            continue
        if (c - cv).xz.length > EYE_AREA_R:
            continue
        dc = np.sqrt((_CPs[:, 0] - c.x) ** 2 + (_CPs[:, 1] - c.z) ** 2).min()
        if dc < W:
            victims.append(f)          # 面心就在带内
            continue
        if RIM_BAND_VERT_CRIT.get(side, True):
            dv = min(np.sqrt((_CPs[:, 0] - v.co.x) ** 2 + (_CPs[:, 1] - v.co.z) ** 2).min() for v in f.verts)
        else:
            dv = 9.9
        if dv < W and dc < 2.5 * W:
            victims.append(f)          # 顶点贴轮廓且面心也不远(粗面小跨界的量) → 必须删, 否则会戳进洞里
            continue
        if dc > 3.0 * W:
            continue                   # 太远, 不可能穿线
        # 面的边是否真的穿过轮廓折线
        hit = False
        fv = [v.co for v in f.verts]
        for k in range(len(fv)):
            a = np.array([fv[k].x, fv[k].z]); b = np.array([fv[(k + 1) % len(fv)].x, fv[(k + 1) % len(fv)].z])
            for t in range(_NCP):
                r = _seg_int_xz(a, b, _CPs[t], _CPs[(t + 1) % _NCP])
                if r:
                    hit = True
                    break
            if hit:
                break
        if hit:
            victims.append(f)          # 该面横跨了轮廓线
    nv0 = len(victims)
    if nv0 < 5:
        bm.free()
        print(f"rebuild_rim_band {side}: 带内仅 {nv0} 面, 跳过")
        return
    if nv0 > RIM_BAND_MAX_FACES:
        bm.free()
        print(f"rebuild_rim_band {side}: 带内 {nv0} 面 > 上限{RIM_BAND_MAX_FACES}, 放弃")
        return
    bmesh.ops.delete(bm, geom=victims, context='FACES')
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # ---- ②/③ 循环: 带外缘细分 → 取边界环; 若不是单一闭环就删掉问题顶点周围的面再试 ----
    def _near_eye(v):
        return (v.co - cv).xz.length < EYE_AREA_R and v.co.y < cy + Y_FRONT_M
    outer = None
    for _try in range(6):
        # ② 带外缘细分到 ≤ARC_MM
        for _ in range(5):
            bm.edges.ensure_lookup_table()
            _la = [e for e in bm.edges if len(e.link_faces) == 1
                   and _near_eye(e.verts[0])
                   and (e.verts[0].co - e.verts[1].co).length > RIM_BAND_ARC_MM / 1000.0]
            if not _la:
                break
            bmesh.ops.subdivide_edges(bm, edges=_la, cuts=1, use_grid_fill=False)
        # ③ 取边界环
        nadj = {}
        for e in bm.edges:
            if len(e.link_faces) != 1:
                continue
            if not _near_eye(e.verts[0]):
                continue
            nadj.setdefault(e.verts[0].index, []).append(e.verts[1].index)
            nadj.setdefault(e.verts[1].index, []).append(e.verts[0].index)
        st = [k for k in nadj if len(nadj[k]) == 2]
        if not st:
            bm.free()
            print(f"rebuild_rim_band {side}: 找不到边界环")
            return
        vmap0 = {v.index: v for v in bm.verts}
        ring = [st[0]]; prev, cur = -1, st[0]
        while cur in nadj:
            cand = [n for n in nadj[cur] if n != prev]
            if not cand:
                break
            nxt = cand[0]
            if nxt == ring[0]:
                break
            ring.append(nxt); prev, cur = cur, nxt
            if len(ring) > 200000:
                break
        if len(ring) == len(st):
            outer = [vmap0[k] for k in ring]
            break
        # 诊断: 把所有环都列出来(大小+质心)
        _seen = set()
        _loops = []
        for _s in st:
            if _s in _seen:
                continue
            _lp = [_s]; _seen.add(_s); _p, _c = -1, _s
            while True:
                _cn = [n for n in nadj[_c] if n != _p and n in vmap0]
                if not _cn:
                    break
                _nx = _cn[0]
                if _nx == _lp[0] or _nx in _seen:
                    break
                _lp.append(_nx); _seen.add(_nx); _p, _c = _c, _nx
                if len(_lp) > 200000:
                    break
            _cx = sum((vmap0[k].co.x - cv.x) for k in _lp) / len(_lp) * 1000
            _cz = sum((vmap0[k].co.z - cv.z) for k in _lp) / len(_lp) * 1000
            _loops.append((len(_lp), _cx, _cz))
        _loops.sort(reverse=True)
        print(f"rebuild_rim_band {side}: 第{_try+1}轮 环清单(顶点数, 质心dx, 质心dz): "
              + "; ".join(f"{n}({a:+.1f},{b:+.1f})" for n, a, b in _loops[:6]))
        # ---- 有分叉/死端: 删掉这些顶点周围的带内面, 再试 ----
        bad = [vmap0[k] for k in nadj if len(nadj[k]) != 2]
        # 也把环尾(走不到的那个顶点)算进去
        if ring and ring[-1] in vmap0:
            bad.append(vmap0[ring[-1]])
        if not bad:
            bm.free()
            print(f"rebuild_rim_band {side}: 边界异常且定位不到问题顶点, 回退")
            return
        bad_xy = [(v.co.x, v.co.z) for v in bad]
        v2 = []
        for f in bm.faces:
            if f.verts and not _near_eye(f.verts[0]):
                continue
            for v in f.verts:
                if any((v.co.x - bx) ** 2 + (v.co.z - bz) ** 2 < (W * 1.6) ** 2 for bx, bz in bad_xy):
                    v2.append(f)
                    break
        if not v2:
            bm.free()
            print(f"rebuild_rim_band {side}: 边界异常(死端 {len(bad)} 个)且无可删面, 回退")
            return
        print(f"rebuild_rim_band {side}: 第{_try+1}轮边界不闭环(走{len(ring)}/{len(st)}), "
              f"删问题顶点周围 {len(v2)} 面后重试")
        bmesh.ops.delete(bm, geom=v2, context='FACES')
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
    if outer is None:
        bm.free()
        print(f"rebuild_rim_band {side}: 6 轮仍无法得到单一闭环边界, 放弃")
        return
    vmap = {v.index: v for v in bm.verts}
    K = len(outer)
    # ---- ③ 内圈 = 手描轮廓, 但【逐个外圈顶点对齐】: 每个外圈点求其在轮廓上的最近参数,
    #         再沿外圈顺序"解绕"成单调 → 内圈与它一一对应, 绝不跨越洞口
    spt_all = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.roll(CP, -1, axis=0) - CP, axis=1))])
    total = spt_all[-1]
    Px = np.append(CP[:, 0], CP[0, 0])
    Pz = np.append(CP[:, 1], CP[0, 1])
    Py = np.append(CY, CY[0])
    raw = []
    for v in outer:
        d = (CP[:, 0] - v.co.x) ** 2 + (CP[:, 1] - v.co.z) ** 2
        raw.append(float(spt_all[int(np.argmin(d))]))
    uu = [raw[0]]
    for _i in range(1, len(raw)):
        d = raw[_i] - uu[-1]
        while d < -total / 2.0:
            d += total
        while d > total / 2.0:
            d -= total
        uu.append(uu[-1] + d)
    if len(uu) > 2 and (uu[-1] - uu[0]) < 0:
        outer = outer[::-1]
        raw = []
        for v in outer:
            d = (CP[:, 0] - v.co.x) ** 2 + (CP[:, 1] - v.co.z) ** 2
            raw.append(float(spt_all[int(np.argmin(d))]))
        uu = [raw[0]]
        for _i in range(1, len(raw)):
            d = raw[_i] - uu[-1]
            while d < -total / 2.0:
                d += total
            while d > total / 2.0:
                d -= total
            uu.append(uu[-1] + d)
    _minstep = total / max(1.0, K) * 0.5
    _mono = [float(uu[0])]
    for _t in range(1, len(uu)):
        _mono.append(max(float(uu[_t]), _mono[-1] + _minstep))
    us = np.mod(np.array(_mono), total)
    X = np.interp(us, spt_all, Px)
    Z = np.interp(us, spt_all, Pz)
    Y = np.interp(us, spt_all, Py)
    inner = []
    for t in range(K):
        inner.append(bm.verts.new(Vector((float(X[t]), float(Y[t]), float(Z[t])))))
    bm.verts.ensure_lookup_table()
    # ---- ④ 一圈条带 ----
    new_faces = []
    made = 0
    failed_k = []
    for k in range(K):
        k2 = (k + 1) % K
        a, b, c, d = inner[k], inner[k2], outer[k2], outer[k]
        ok = 0
        for tri in ((a, b, c), (a, c, d)):
            try:
                new_faces.append(bm.faces.new(tri)); made += 1; ok += 1
            except ValueError:
                pass
        if ok < 2:      # 三角失败 → 直接建整块四边形(不要换对角线, 那会把 rim 盖到自己身上)
            try:
                new_faces.append(bm.faces.new((a, b, c, d))); made += 1; ok += 1
            except ValueError:
                pass
        if ok == 0:
            failed_k.append(k)
    # ---- ⑤ 逐面定向: 与共顶点的【非新建面】平均法线比对(避免整圈判据被污染) ----
    bm.faces.ensure_lookup_table()
    bm.normal_update()   # 关键: 新建面的 f.normal 是惰性的, 不 update 会读到旧/零值 → 定向判据全部误判
    # ---- ⑤ 定向: 用【眼周皮肤面的稳健多数法线】统一给新面定向 ----
    # (先平均→只保留与平均同向的再平均 = 排除少数异向面; 绝不能写成 ref=-ref, 那等于不翻转)
    _fl = [f.normal.copy() for f in bm.faces
           if f not in new_faces
           and (f.calc_center_median() - cv).xz.length < EYE_AREA_R
           and f.calc_center_median().y < -0.020]
    gref = Vector((0.0, 0.0, 0.0))
    for n in _fl:
        gref += n
    if gref.length > 1e-12:
        g0 = gref.normalized()
        gref = Vector((0.0, 0.0, 0.0))
        for n in _fl:
            if n.dot(g0) > 0:
                gref += n
    if gref.length < 1e-12:
        gref = Vector((0.0, -1.0, 0.0))
    gref.normalize()
    _nflip = 0
    for f in new_faces:
        # 双重判据: ①与多数皮肤法线相反 ②法线朝后(+Y)=用户在面朝向显示里看到的红
        if f.normal.dot(gref) < 0 or f.normal.y > 0.05:
            f.normal_flip()
            _nflip += 1
        f.smooth = True
    bm.normal_update()
    # 复核(独立判据): 翻转后再查一遍朝后的面数
    _still = sum(1 for f in new_faces if f.normal.y > 0.05)
    print(f"rebuild_rim_band {side}: 新面定向 基准={len(_fl)}皮肤面 多数法线({gref.y:+.2f}), "
          f"翻转 {_nflip}/{len(new_faces)}, 复查仍朝后 {_still}")
    # ---- ⑥ 收尾定向(源头修): 眼区前表面里【与皮肤多数朝向相反】的面一律翻正 ——
    #      包括本次编辑产生的和原网格自带的遗留反面(用户面朝向显示里会显示为红)
    bm.normal_update()
    _fixall = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if (c - cv).xz.length > EYE_AREA_R or c.y > Y_BACK_SPLIT:   # 只排除后脑(眼周皮肤在 -0.09~-0.13)
            continue
        # 判据与用户看到的一致: 正视相机下 法线朝后(+Y) = 面朝向显示里的红
        if f.normal.y > RIM_BAND_FLIP_Y:
            f.normal_flip()
            _fixall += 1
    bm.normal_update()
    _left = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if (c - cv).xz.length > EYE_AREA_R or c.y > Y_BACK_SPLIT:
            continue
        if f.normal.y > RIM_BAND_FLIP_Y:
            _left += 1
    print(f"rebuild_rim_band {side}: 收尾定向(法线朝后) 翻正 {_fixall} 面, 复查残留 {_left}")
    # ---- ⑦ 收尾清理(为后续 QR 准备): n-gon 三角化 / 重复顶点焊接 / 全部 smooth ----
    def _eye_face(f):
        c = f.calc_center_median()
        return (c - cv).xz.length < 3.0 * EYE_AREA_R and c.y < Y_BACK_SPLIT
    _ng = [f for f in bm.faces if _eye_face(f) and len(f.verts) > 4]
    if _ng:
        try:
            bmesh.ops.triangulate(bm, faces=_ng, quad_method='BEAUTY', ngon_method='BEAUTY')
            print(f"rebuild_rim_band {side}: n-gon 三角化 {len(_ng)} 面")
        except Exception as _e:
            print(f"rebuild_rim_band {side}: n-gon 三角化失败 {_e}")
    # ---- ⑦b 长边细分: 缝合时内圈密/外圈疏 → 拉出 >3mm 长条(用户实测最长 9.29mm) ----
    # 只改这段的三角化密度, 不动几何形状(QR 需要均匀细网格)
    _lc = 0
    _thresh = max(0.0012, RIM_SKIN_EDGE_M * 1.05)  # ≈皮肤边长: 缝合带与皮肤同密度(用户: 带内过密会发黑)
    for _round in range(4):
        _lng = set()
        for f in bm.faces:
            c = f.calc_center_median()
            if (c - cv).xz.length > 0.030 or c.y > Y_BACK_SPLIT:
                continue
            if float(np.sqrt((CP[:, 0] - c.x) ** 2 + (CP[:, 1] - c.z) ** 2).min()) > 0.008:
                continue
            for e in f.edges:
                if e.calc_length() > _thresh:
                    _lng.add(e)
        if not _lng:
            break
        try:
            bmesh.ops.subdivide_edges(bm, edges=list(_lng), cuts=1, use_grid_fill=False)
            _lc += len(_lng)
        except Exception as _e:
            print(f"rebuild_rim_band {side}: 长边细分失败 {_e}")
            break
        bm.normal_update()
        _ng2 = [f for f in bm.faces if len(f.verts) > 4 and (f.calc_center_median() - cv).xz.length < 0.030
                and f.calc_center_median().y < Y_BACK_SPLIT
                and float(np.sqrt((CP[:, 0] - f.calc_center_median().x) ** 2
                                  + (CP[:, 1] - f.calc_center_median().z) ** 2).min()) <= 0.008]
        if _ng2:
            bmesh.ops.triangulate(bm, faces=_ng2, quad_method='BEAUTY', ngon_method='BEAUTY')
    if _lc:
        print(f"rebuild_rim_band {side}: 长边细分 {_lc} 条")
    # ---- ⑦c 最终 n-gon 清扫: 迭代到 0(细分会顺带产生 n-gon; QR 输入不应含 >4 边面) ----
    for _round in range(6):
        _ng3 = [f for f in bm.faces if len(f.verts) > 4 and _eye_face(f)]
        if not _ng3:
            break
        try:
            bmesh.ops.triangulate(bm, faces=_ng3, quad_method='BEAUTY', ngon_method='BEAUTY')
        except Exception as _e:
            print(f"rebuild_rim_band {side}: 最终 n-gon 清扫失败 {_e}")
            break
    _ngleft = sum(1 for f in bm.faces if len(f.verts) > 4 and _eye_face(f))
    print(f"rebuild_rim_band {side}: 最终 n-gon 残留 {_ngleft}")
    # ---- ⑦d 二次定向: ⑦b/⑦c 的细分/三角化会新建面(新面绕序可能仍朝后) → 再扫一遍 ----
    bm.normal_update()
    _fix2 = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if (c - cv).xz.length > EYE_AREA_R or c.y > Y_BACK_SPLIT:
            continue
        if f.normal.y > RIM_BAND_FLIP_Y:
            f.normal_flip()
            _fix2 += 1
    bm.normal_update()
    _left2 = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if (c - cv).xz.length > EYE_AREA_R or c.y > Y_BACK_SPLIT:
            continue
        if f.normal.y > RIM_BAND_FLIP_Y:
            _left2 += 1
    print(f"rebuild_rim_band {side}: 细分后二次定向 翻正 {_fix2} 面, 残留 {_left2}")
    # ---- ⑦e 退化面清除: 极短边/零面积面(QR 直接会出错的东西) ----
    _de = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_length() < 0.00008
           and (e.verts[0].co - cv).xz.length < 3.0 * EYE_AREA_R
           and e.verts[0].co.y < Y_BACK_SPLIT
           and (e.verts[1].co - cv).xz.length < 3.0 * EYE_AREA_R
           and e.verts[1].co.y < Y_BACK_SPLIT]
    if _de:
        try:
            bmesh.ops.dissolve_degenerate(bm, dist=0.00008, edges=_de)
            print(f"rebuild_rim_band {side}: 退化边清除 {len(_de)} 条")
        except Exception as _e:
            print(f"rebuild_rim_band {side}: 退化边清除失败 {_e}")
    _MOVED = set()
    # ---- ⑦f 局部表面松弛(用户: 左眼下睑外侧不圆/多凸起, 参考右眼曲率) ----
    # 只动"离轮廓 <2.5mm"的前表面顶点; 锚定权重随距离衰减(远处不动 → 不产生新棱);
    # 位移硬上限 RIM_RELAX_MAX_MM。目的: 去掉缝合带与粗面台阶造成的波浪/褶皱。
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    _r_sm = 0.0025
    _near = []
    for v in bm.verts:
        if v.co.y >= Y_BACK_SPLIT or (v.co - cv).xz.length > 2.5 * EYE_AREA_R:
            continue
        _dd = float(np.sqrt((CP[:, 0] - v.co.x) ** 2 + (CP[:, 1] - v.co.z) ** 2).min())
        if _dd < _r_sm:
            _near.append((v.index, _dd))
    try:
      if len(_near) > 40:
        _idx = {vi: i for i, (vi, _) in enumerate(_near)}
        _co0 = np.array([bm.verts[vi].co[:] for vi, _ in _near])
        _w = np.exp(-(np.array([d for _, d in _near]) / 0.0012) ** 2)   # 锚定权重
        _ed = []
        for e in bm.edges:
            a, b = e.verts[0].index, e.verts[1].index
            if a in _idx and b in _idx:
                _ed.append((_idx[a], _idx[b]))
        if _ed:
            _ea = np.array([x for x, _ in _ed]); _eb = np.array([y for _, y in _ed])
            _deg = np.zeros(len(_near))
            np.add.at(_deg, _ea, 1.0); np.add.at(_deg, _eb, 1.0)
            _deg[_deg == 0] = 1.0
            _co = _co0.copy()
            for _it in range(30):
                _acc = np.zeros_like(_co)
                np.add.at(_acc, _ea, _co[_eb]); np.add.at(_acc, _eb, _co[_ea])
                _lap = _acc / _deg[:, None]
                _co = _co + 0.45 * _w[:, None] * (_lap - _co)
            _dvec = _co - _co0
            _dl = np.linalg.norm(_dvec, axis=1)
            _mx = 0.00045                       # 位移硬上限 0.45mm
            _sc = np.where(_dl > _mx, _mx / np.maximum(_dl, 1e-12), 1.0)
            _co = _co0 + _dvec * _sc[:, None]
            for vi, i in _idx.items():
                bm.verts[vi].co = _co[i]
                _MOVED.add(vi)
            bm.normal_update()
            print(f"rebuild_rim_band {side}: 局部松弛 {len(_near)} 顶点 位移max{min(_dl.max(), _mx)*1000:.3f}mm")
    except Exception as _e:
        print(f"rebuild_rim_band {side}: 局部松弛失败(已跳过) {_e}")
    # ---- ⑦f2 松弛后再清一次退化边 + 短边焊接(松弛会把顶点挪近, 产生新的微折角) ----
    _de2 = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_length() < 0.00008
            and (e.verts[0].co - cv).xz.length < 3.0 * EYE_AREA_R
            and e.verts[0].co.y < Y_BACK_SPLIT
            and (e.verts[1].co - cv).xz.length < 3.0 * EYE_AREA_R
            and e.verts[1].co.y < Y_BACK_SPLIT]
    if _de2:
        try:
            bmesh.ops.dissolve_degenerate(bm, dist=0.00008, edges=_de2)
            print(f"rebuild_rim_band {side}: 松弛后退化清除 {len(_de2)} 条")
        except Exception as _e:
            print(f"rebuild_rim_band {side}: 松弛后退化清除失败 {_e}")
    # 环上 >60° 的微折角: 把折角顶点向两侧邻点中点收(只动亚毫米)
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    try:
      for _rnd in range(3):
        _oe2 = [e for e in bm.edges if len(e.link_faces) == 1
                and (e.verts[0].co - cv).xz.length < 0.05 and e.verts[0].co.y < Y_BACK_SPLIT]
        _dg = {}
        for e in _oe2:
            a, b = e.verts[0], e.verts[1]
            _dg.setdefault(a.index, []).append(b.index)
            _dg.setdefault(b.index, []).append(a.index)
        _fixed = 0
        for vi, nb in _dg.items():
            if len(nb) != 2:
                continue
            a = bm.verts[vi].co; b1 = bm.verts[nb[0]].co; b2 = bm.verts[nb[1]].co
            v1 = a - b1; v2 = b2 - a
            if v1.length < 1e-9 or v2.length < 1e-9:
                continue
            ang = np.degrees(np.arccos(np.clip(v1.normalized().dot(v2.normalized()), -1, 1)))
            if ang > 60:
                mid = (b1 + b2) * 0.5
                bm.verts[vi].co = a + (mid - a) * 0.35
                _fixed += 1
        if not _fixed:
            break
      if _fixed:
        print(f"rebuild_rim_band {side}: 环微折角收拢 {_fixed} 个")
    except Exception as _e:
        print(f"rebuild_rim_band {side}: 微折角收拢失败(已跳过) {_e}")
    bm.normal_update()
    # ---- ⑦h 环 XZ 低通(去 1~3mm 尺度抖动; 纯算法, 输入=本模型自身几何) ----
    # 用户要求: 不依赖任何人工画的线 —— 目标曲率=环自身在 2.8mm 高斯下的低频重建,
    # 位移上限 0.6mm。保留眼睛整体弧度, 只抹掉边缘的小波浪。
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    try:
        _oe3 = [e for e in bm.edges if len(e.link_faces) == 1
                and (e.verts[0].co - cv).xz.length < 0.05 and e.verts[0].co.y < Y_BACK_SPLIT]
        _dg3 = {}
        for e in _oe3:
            a_, b_ = e.verts[0], e.verts[1]
            _dg3.setdefault(a_.index, []).append(b_.index)
            _dg3.setdefault(b_.index, []).append(a_.index)
        _st3 = [k for k in _dg3 if len(_dg3[k]) == 2]
        if _st3:
            ring3 = [_st3[0]]; _prev, _cur = -1, _st3[0]
            while True:
                _cand = [n for n in _dg3[_cur] if n != _prev]
                if not _cand or _cand[0] == ring3[0]:
                    break
                ring3.append(_cand[0]); _prev, _cur = _cur, _cand[0]
            if len(ring3) > 40:
                P3 = np.array([bm.verts[k].co[:] for k in ring3])
                n3 = len(ring3)
                _d3 = np.linalg.norm(np.roll(P3, -1, axis=0) - P3, axis=1)
                sp3 = np.concatenate([[0.0], np.cumsum(_d3)[:-1]])
                per3 = sp3[-1] + _d3[-1]
                sig = 0.0028
                SX = np.zeros(n3); SZ = np.zeros(n3)
                for i in range(n3):
                    ds = np.abs(sp3 - sp3[i]); ds = np.minimum(ds, per3 - ds)
                    w = np.exp(-0.5 * (ds / sig) ** 2)
                    SX[i] = (P3[:, 0] * w).sum() / w.sum()
                    SZ[i] = (P3[:, 2] * w).sum() / w.sum()
                ddx = SX - P3[:, 0]; ddz = SZ - P3[:, 2]
                dl = np.sqrt(ddx ** 2 + ddz ** 2)
                cap = 0.0006
                sc = np.where(dl > cap, cap / np.maximum(dl, 1e-12), 1.0)
                mv = 0.0
                for i, k in enumerate(ring3):
                    v = bm.verts[k]
                    v.co = Vector((v.co.x + float(ddx[i] * sc[i]), v.co.y, v.co.z + float(ddz[i] * sc[i])))
                    _MOVED.add(k)
                    mv = max(mv, float(dl[i] * sc[i]))
                bm.normal_update()
                print(f"rebuild_rim_band {side}: 环XZ低通 {n3} 点 平均位移{dl.mean()*1000:.3f}mm 最大{mv*1000:.3f}mm")
    except Exception as _e:
        print(f"rebuild_rim_band {side}: 环XZ低通失败(已跳过) {_e}")
    # ---- ⑦g 折叠面翻转: 面法线与邻面平均相反(=用户看到的红/黑错乱面) ----
    bm.normal_update()
    _fold = 0
    for f in bm.faces:
        c0 = f.calc_center_median()
        if (c0 - cv).xz.length > 3.0 * EYE_AREA_R or c0.y > Y_BACK_SPLIT:
            continue
        acc = Vector((0.0, 0.0, 0.0)); wsum = 0.0
        for e in f.edges:
            for g in e.link_faces:
                if g is f:
                    continue
                acc += g.normal * g.calc_area(); wsum += g.calc_area()
        if wsum <= 0:
            continue
        if f.normal.dot(acc) < 0:
            f.normal_flip(); _fold += 1
    bm.normal_update()
    if _fold:
        print(f"rebuild_rim_band {side}: 折叠面翻转 {_fold} 面")
    _ev = [v for v in bm.verts if (v.co - cv).xz.length < 3.0 * EYE_AREA_R and v.co.y < Y_BACK_SPLIT]
    if _ev:
        try:
            bmesh.ops.remove_doubles(bm, verts=_ev, dist=RIM_WELD_MM / 1000.0 * 0.5)
        except Exception:
            pass
    bm.normal_update()
    _smooth = 0
    _nonquad = 0
    for f in bm.faces:
        if not _eye_face(f):
            continue
        if not f.smooth:
            f.smooth = True
            _smooth += 1
        if len(f.verts) > 4:
            _nonquad += 1
    print(f"rebuild_rim_band {side}: 收尾清理 三角化n-gon后残留>4边 {_nonquad}, 补smooth {_smooth} 面")
    bm.to_mesh(mesh)
    bm.free()
    try:
        bm_pre.free()
    except Exception:
        pass
    mesh.update()
    if obj.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
    print(f"rebuild_rim_band {side}: 删带内皮肤面 {nv0}, 外缘 {K} 顶点(细分≤{RIM_BAND_ARC_MM}mm), "
          f"内圈=手描轮廓 {K} 点, 新建面 {made}, 未能闭合格 {len(failed_k)}")
    if failed_k:
        _fk = failed_k[:6]
        print("   未闭合格位置: " + "; ".join(f"dx{(inner[i].co.x-cv.x)*1000:+.2f} dz{(inner[i].co.z-cv.z)*1000:+.2f}" for i in _fk))


def rebuild_rim_patch(obj, center, side, poly, R_out_mm=3.5, inner_tol_mm=0.35):
    """v73(D): 折返处 rim 边界重建（用户方案 D）.

    问题: 切割面沿 Y 垂直切, 遇到"近垂直鼓包"时边界绕鼓包出去又折回 → XZ 上自交(折返尖)。
    做法: ①删掉折返处围绕 rim 的一小片皮肤面(圆盘 R_out)
          ②该处边界变成"轮廓段 + 圆盘外弧"
          ③沿手描轮廓重建内圈(深度取弧长低通, 消掉鼓包造成的深度尖)
          ④内圈与圆盘外弧按弧长缝合 → rim 环回到手描轮廓, 皮肤自轮廓向外一圈新面光滑过渡
    圆盘之外的皮肤一个顶点不动。
    验收: 折返数 0 / 无非流形 / 轮廓偏差 ≤0.2mm。
    """
    if not RIM_PATCH_ENABLE:
        return
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    inner_tol = inner_tol_mm / 1000.0
    mesh = obj.data

    # ---- 0. 预取: 手描轮廓(切割用的那条)每点沿 Y 打到原表面的深度 ----
    cy = cv.y
    y_ray = cy - 0.080
    CP = []
    for (px, pz) in poly:
        ok, loc, nor, idx = obj.ray_cast(Vector((float(px), y_ray, float(pz))), Vector((0.0, 1.0, 0.0)))
        CP.append(Vector((float(px), loc.y if ok else cy, float(pz))))
    CPn = np.array([[p.x, p.z] for p in CP])
    NP = len(CP)

    # ---- 0b. 自动定位折返: 用原环的 XZ 自交点算圆盘圆心 + 半径 ----
    bm0 = bmesh.new()
    bm0.from_mesh(mesh)
    bm0.verts.ensure_lookup_table()
    bm0.edges.ensure_lookup_table()
    nadj0 = {}
    for e in bm0.edges:
        if len(e.link_faces) != 1:
            continue
        if (e.verts[0].co - cv).xz.length > EYE_AREA_R or e.verts[0].co.y > cy + Y_FRONT_M:
            continue
        nadj0.setdefault(e.verts[0].index, []).append(e.verts[1].index)
        nadj0.setdefault(e.verts[1].index, []).append(e.verts[0].index)
    st0 = [k for k in nadj0 if len(nadj0[k]) == 2]
    if not st0:
        bm0.free()
        return
    ring0 = [st0[0]]; prev0, cur0 = -1, st0[0]
    while cur0 in nadj0:
        cand = [n for n in nadj0[cur0] if n != prev0]
        if not cand:
            break
        nxt = cand[0]
        if nxt == ring0[0]:
            break
        ring0.append(nxt); prev0, cur0 = cur0, nxt
        if len(ring0) > 100000:
            break
    v0 = {v.index: v for v in bm0.verts}
    if any(k not in v0 for k in ring0):
        bm0.free()
        return
    Q0 = np.array([[v0[k].co.x, v0[k].co.z] for k in ring0]) * 1000.0
    N0 = len(ring0)
    hits = []
    for i in range(N0):
        a1, a2 = Q0[i], Q0[(i + 1) % N0]
        for j in range(i + 2, N0):
            if (j + 1) % N0 == i or j == (i + 1) % N0:
                continue
            r = _seg_int_xz(a1, a2, Q0[j], Q0[(j + 1) % N0])
            if r:
                hits.append((i, j, r))
    bm0.free()
    if not hits:
        print(f"rebuild_rim_patch {side}: 环无折返, 跳过")
        return
    pts = []
    idx_inv = set()
    for i, j, (t, u) in hits:
        pts.append(Q0[i] + (Q0[(i + 1) % N0] - Q0[i]) * t)
        idx_inv.update([i, (i + 1) % N0, j, (j + 1) % N0])
    # 折返可能有多簇(实测 L 有两簇, 相距 ~5.5mm) → 本次只处理【最密的一簇】, 靠外层循环多次调用
    P = np.array(pts)
    used = [False] * len(P)
    clusters = []
    for a in range(len(P)):
        if used[a]:
            continue
        grp = [a]; used[a] = True
        changed = True
        while changed:
            changed = False
            for b in range(len(P)):
                if used[b]:
                    continue
                if min(float(np.linalg.norm(P[b] - P[c])) for c in grp) < RIM_PATCH_CLUSTER_MM:
                    grp.append(b); used[b] = True; changed = True
        clusters.append(grp)
    clusters.sort(key=len, reverse=True)
    grp = clusters[0]
    print(f"rebuild_rim_patch {side}: 折返 {len(hits)} 处 / {len(clusters)} 簇, 本次处理最大簇({len(grp)} 处)")
    ctr_xz = np.mean(P[grp], axis=0)
    ext = max(float(np.linalg.norm(Q0[k] - ctr_xz)) for k in idx_inv)
    R_out = (ext + RIM_PATCH_PAD_MM) / 1000.0
    if R_out * 1000.0 > RIM_PATCH_MAX_R_MM:
        print(f"rebuild_rim_patch {side}: 圆盘 R={R_out*1000:.2f}mm 超过上限{RIM_PATCH_MAX_R_MM}mm, 放弃(避免大改)")
        return
    ctr = Vector((float(ctr_xz[0] / 1000.0), cv.y, float(ctr_xz[1] / 1000.0)))
    print(f"rebuild_rim_patch {side}: 折返 {len(hits)} 处, 圆心(dx{ctr_xz[0]-cv.x*1000:+.2f},"
          f"dz{ctr_xz[1]-cv.z*1000:+.2f})mm, 跨度 {ext:.2f}mm → 圆盘 R={R_out*1000:.2f}mm")

    # ---- 1. 删圆盘内的皮肤面 ----
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    victims = []
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y > cy + Y_FRONT_M:
            continue
        if (c - cv).xz.length > EYE_AREA_R:
            continue
        if (c - ctr).xz.length < R_out:
            victims.append(f)
    nv0 = len(victims)
    if nv0 > RIM_PATCH_MAX_FACES:
        bm.free()
        print(f"rebuild_rim_patch {side}: 圆盘内 {nv0} 面 > 上限{RIM_PATCH_MAX_FACES}, 放弃(避免大改)")
        return
    if not victims:
        bm.free()
        print(f"rebuild_rim_patch {side}: 圆盘内没有面, 跳过")
        return
    old_verts = set(bm.verts)      # 删面前记录顶点引用: 存活者=原环(内), 新建者=圆盘边界(外)
    bmesh.ops.delete(bm, geom=victims, context='FACES')
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # ---- 1b. 圆盘周界的长边先细分到 ≤RIM_PATCH_ARC_MM(否则缝合面会出现 5mm 长条 → 假折返) ----
    for _sa in range(4):
        bm.edges.ensure_lookup_table()
        _la = [e for e in bm.edges if len(e.link_faces) == 1
               and (e.verts[0].co - cv).xz.length < EYE_AREA_R
               and e.verts[0].co.y < cy + Y_FRONT_M
               and (e.verts[0].co - e.verts[1].co).length > RIM_PATCH_ARC_MM / 1000.0]
        if not _la:
            break
        bmesh.ops.subdivide_edges(bm, edges=_la, cuts=1, use_grid_fill=False)

    # ---- 2. 取眼周开放边, 分环 ----
    oedges = [e for e in bm.edges if len(e.link_faces) == 1
              and (e.verts[0].co - cv).xz.length < EYE_AREA_R
              and e.verts[0].co.y < cy + Y_FRONT_M]
    if not oedges:
        bm.free()
        print(f"rebuild_rim_patch {side}: 删面后找不到开放边, 回退")
        return
    nadj = {}
    for e in oedges:
        for a, b in ((e.verts[0], e.verts[1]), (e.verts[1], e.verts[0])):
            nadj.setdefault(a.index, []).append(b.index)
    st = [k for k in nadj if len(nadj[k]) == 2]
    ring = [st[0]]; prev, cur = -1, st[0]
    while cur in nadj:
        cand = [n for n in nadj[cur] if n != prev]
        if not cand:
            break
        nxt = cand[0]
        if nxt == ring[0]:
            break
        ring.append(nxt); prev, cur = cur, nxt
        if len(ring) > 100000:
            break
    vmap = {v.index: v for v in bm.verts}
    if len(ring) != len(st) or any(k not in vmap for k in ring):
        n_loops = len(st) - len(ring) + 1
        print(f"rebuild_rim_patch {side}: 边界不是单一闭环(环上{len(ring)}/{len(st)}顶点), 回退")
        bm.free()
        return

    # ---- 3. 分类: 贴轮廓(内) / 圆盘外弧(外) ----
    def d2contour(x, z):
        d = np.sqrt((CPn[:, 0] - x) ** 2 + (CPn[:, 1] - z) ** 2)
        i = int(np.argmin(d))
        return float(d[i]), i

    cls = []
    for k in ring:
        v = vmap[k]
        d, ci = d2contour(v.co.x, v.co.z)
        cls.append((d < inner_tol, ci, d))
    _dmax = max(c[2] for c in cls) * 1000.0
    _dmin = min(c[2] for c in cls) * 1000.0
    n_out = sum(1 for c in cls if not c[0])
    if n_out == 0 or n_out == len(ring):
        bm.free()
        print(f"rebuild_rim_patch {side}: 分类异常(外弧 {n_out}/{len(ring)}), 回退")
        return
    # 外弧 = 一段连续 run。注意: 必须从"内"点起算, 否则跨越 0 号索引的 run 会被算成两段
    M0 = len(ring)
    _s0 = next(i for i, c in enumerate(cls) if c[0])
    order = [(_s0 + t) % M0 for t in range(M0)]
    runs = []
    _cur = None
    for t, idx in enumerate(order):
        if not cls[idx][0]:
            _cur = [t] if _cur is None else (_cur + [t])
        elif _cur is not None:
            runs.append(_cur); _cur = None
    if _cur is not None:
        runs.append(_cur)
    if len(runs) != 1:
        print(f"rebuild_rim_patch {side}: 外弧 {len(runs)} 段(期望1段), 回退 "
              f"[环上到轮廓距离 min{_dmin:.3f}/max{_dmax:.3f}mm, 阈值{inner_tol*1000:.2f}mm]")
        bm.free()
        return
    outer_pos = runs[0]
    a_p, b_p = outer_pos[0], outer_pos[-1]
    N = len(ring)
    ja = ring[order[(a_p - 1) % M0]]      # 外弧之前的环点(交界 A)
    jb = ring[order[(b_p + 1) % M0]]      # 外弧之后的环点(交界 B)
    n_out_v = len(outer_pos)
    outer_idx = [ring[order[p]] for p in outer_pos]
    _, ia = d2contour(vmap[ja].co.x, vmap[ja].co.z)
    _, ib = d2contour(vmap[jb].co.x, vmap[jb].co.z)
    _, ic = d2contour(ctr.x, ctr.z)
    # 从 ia 走到 ib, 使其经过圆盘中心对应的轮廓点 ic
    def _fwd(x, y, n):
        return (y - x) % n
    if _fwd(ia, ic, NP) <= _fwd(ia, ib, NP):
        seq = [(ia + s) % NP for s in range(0, _fwd(ia, ib, NP) + 1)]
    else:
        seq = [(ia - s) % NP for s in range(0, _fwd(ib, ia, NP) + 1)][::-1]
    if len(seq) < 2:
        bm.free()
        print(f"rebuild_rim_patch {side}: 轮廓段太短, 回退")
        return
    # ---- 4. 内圈深度: 弧长低通, 两端拉回交界点真实 y ----
    ys = np.array([CP[i].y for i in seq], dtype=np.float64)
    y0 = ys.copy()
    dmax = 0.0
    for _ in range(RIM_PATCH_DEPTH_PASSES):
        nxt = 0.5 * (np.roll(ys, 1) + np.roll(ys, -1))
        dev = float(np.abs(nxt - y0).max()) * 1000.0
        if dev > RIM_PATCH_DEPTH_CAP_MM:
            break
        ys = nxt
        dmax = dev
    corr = ys - y0
    m = len(seq)
    ramp = np.minimum(np.arange(m), np.arange(m)[::-1])
    ramp = np.clip(ramp / max(1.0, RIM_PATCH_RAMP), 0.0, 1.0)
    ys = y0 + corr * ramp
    ya_real = vmap[ja].co.y
    yb_real = vmap[jb].co.y
    ys[0] = ya_real
    ys[-1] = yb_real
    if m > 2:
        ys[1] = 0.5 * (ya_real + ys[1])
        ys[-2] = 0.5 * (yb_real + ys[-2])

    # ---- 5. 内圈按【外弧点数】重采样 + 标准条带三角化(保证无跳过/无长边) ----
    outer = [vmap[k] for k in outer_idx]
    K = len(outer)
    if K < 3:
        bm.free()
        print(f"rebuild_rim_patch {side}: 外弧太短({K}), 回退")
        return
    # 用统一走法确定 inner/outer 的方向
    if (outer[0].co - vmap[ja].co).length > (outer[-1].co - vmap[ja].co).length:
        outer = outer[::-1]
    pick_t = np.linspace(0.0, float(m - 1), K)
    pick_i = [seq[int(round(t))] for t in pick_t]
    pick_y = np.interp(pick_t, np.arange(m), ys)
    inner = []
    for t in range(K):
        if t == 0:
            inner.append(vmap[ja])
        elif t == K - 1:
            inner.append(vmap[jb])
        else:
            v = bm.verts.new(Vector((CP[pick_i[t]].x, float(pick_y[t]), CP[pick_i[t]].z)))
            inner.append(v)
    bm.verts.ensure_lookup_table()
    new_faces = []
    made = 0
    for k in range(K - 1):
        quad = (inner[k], inner[k + 1], outer[k + 1], outer[k])
        try:
            new_faces.append(bm.faces.new(quad[:3]))
            made += 1
        except ValueError:
            pass
        try:
            new_faces.append(bm.faces.new((quad[0], quad[2], quad[3])))
            made += 1
        except ValueError:
            pass
    if True:
        pass
    # ---- 6. 只对新建面统一朝外法线(绝不能动整个网格的面!) ----
    bm.faces.ensure_lookup_table()
    nrm = Vector((0.0, 0.0, 0.0))
    for k in outer_idx:
        v = vmap[k]
        for f in v.link_faces:
            if f not in new_faces:
                nrm += f.normal
    if nrm.length < 1e-9:
        nrm = Vector((0.0, -1.0, 0.0))
    nrm.normalize()
    for f in new_faces:
        if f.normal.dot(nrm) < 0:
            f.normal_flip()
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"rebuild_rim_patch {side}: 删皮肤面 {nv0}, 圆盘外弧 {n_out_v} 顶点, 轮廓段 {m} 点"
          f"(深度低通 {dmax:.3f}mm/上限{RIM_PATCH_DEPTH_PASSES}passes), 新建面 {made}")


def remove_ring_folds(obj, center, side, max_iter=10):
    """v70: 去掉 rim 环在 XZ 上的【自交折返小尖】.

    根因(实测 _q_fold.py): L 环有 6 处 XZ 自交, 全部集中在"下睑外侧"那 3mm; R 环 0 处。
    这是切割面切到"近乎与前视图平行"的陡面时, 边界出去又折回留下的尖 —— 用户看到的"缺口"就是它,
    也是那 37.7~127° 3D 转角的真正来源(不是深度起伏)。
    做法: 找自交的两条边 → 在交点处各切一刀 → 删掉两切点之间那段小环(连同其面) → 合并两切点。
    不动表面、不动轮廓线、不动其余顶点。
    """
    if not RIM_REMOVE_FOLDS:
        return
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    def get_ring(bm):
        nadj = {}
        for v in bm.verts:
            if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
                continue
            nb = [e.other_vert(v).index for e in v.link_edges if len(e.link_faces) == 1]
            if len(nb) == 2:
                nadj[v.index] = nb
        st = [k for k in nadj if len(nadj[k]) == 2]
        if not st:
            return []
        ring = [st[0]]; prev, cur = -1, st[0]
        while cur in nadj:
            cand = [n for n in nadj[cur] if n != prev]
            if not cand:
                break
            nxt = cand[0]
            if nxt == ring[0]:
                break
            ring.append(nxt); prev, cur = cur, nxt
            if len(ring) > 100000:
                break
        return ring

    def seg_int(p1, p2, p3, p4):
        d1 = p2 - p1; d2 = p4 - p3
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-14:
            return None
        t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
        u = ((p3[0] - p1[0]) * d1[1] - (p3[1] - p1[1]) * d1[0]) / den
        if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
            return (t, u)
        return None

    fixed = 0
    for _ in range(max_iter):
        bm = bmesh.from_edit_mesh(mesh)
        try:
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
        except Exception:
            break
        ring = get_ring(bm)
        N = len(ring)
        if N < 8:
            break
        vmap = {v.index: v for v in bm.verts}
        if any(k not in vmap for k in ring):
            break
        Q = np.array([[vmap[k].co.x, vmap[k].co.z] for k in ring]) * 1000.0
        best = None
        for i in range(N):
            a1, a2 = Q[i], Q[(i + 1) % N]
            for j in range(i + 2, N):
                if (j + 1) % N == i or j == (i + 1) % N:
                    continue
                b1, b2 = Q[j], Q[(j + 1) % N]
                r = seg_int(a1, a2, b1, b2)
                if r:
                    loop = min(j - i, N - (j - i))
                    if best is None or loop < best[0]:
                        best = (loop, i, j, r)
        if best is None:
            break
        loop, i, j, (t, u) = best
        # 折返段 = 两条相交边之间较短的一段(顶点 i+1 .. j)
        M = N
        fwd = (j - (i + 1)) % M
        if fwd <= M - fwd:
            seg_idx = [(i + 1 + s) % M for s in range(0, fwd + 1)]
            keep_a, keep_b = ring[i], ring[(j + 1) % M]
        else:
            seg_idx = [(j + 1 + s) % M for s in range(0, (M - fwd - 1) + 1)]
            keep_a, keep_b = ring[j], ring[(i + 1) % M]
        victims = [vmap[k] for k in seg_idx if k in vmap]
        if not victims:
            break
        bmesh.ops.delete(bm, geom=victims, context='VERTS')
        bmesh.update_edit_mesh(mesh)
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        vmap3 = {v.index: v for v in bm.verts}
        if keep_a in vmap3 and keep_b in vmap3:
            bmesh.ops.weld_verts(bm, targetmap={vmap3[keep_b]: vmap3[keep_a]})
            bmesh.update_edit_mesh(mesh)
        fixed += 1
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"remove_ring_folds {side}: 修复折返 {fixed} 处")


def rebuild_ring_arc_length(obj, center, side):
    """v68: rim 环重建 —— ①把环顶点按【等弧长】重新分布(XZ 仍严格沿原环走向=手描线) ②深度 y 按弧长低通.

    根因(实测): 环顶点间距 0.06~0.60mm 极不均 → 任何深度起伏都会被放大成忽大忽小的 3D 转角;
    之前"按索引低通深度"失败就是因为在非等距索引上做低通 = 在弧长上打阶梯。
    本函数: 重采样成等弧长间距(总长不变) → 深度用等距 Laplacian 低通(带 |Δy| 上限) → 环成为
    "轮廓曲率+平滑深度斜率"的光滑曲线。XZ 不偏离、表面不动、轮廓线不动。
    代价: 环在该处会略微离面(最大 LIFT_MAX), 即洞的边不再逐点贴在皮肤上(视觉上是零点几毫米)。
    """
    if not RIM_REBUILD_RING:
        return
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    nadj = {}
    for v in bm.verts:
        if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
            continue
        nb = [e.other_vert(v).index for e in v.link_edges if len(e.link_faces) == 1]
        if len(nb) == 2:
            nadj[v.index] = nb
    # 排序成闭环
    st = [k for k in nadj if len(nadj[k]) == 2]
    if not st:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"rebuild_ring_arc_length {side}: 未找到环")
        return
    ring = [st[0]]; prev, cur = -1, st[0]
    while cur in nadj:
        cand = [n for n in nadj[cur] if n != prev]
        if not cand:
            break
        nxt = cand[0]
        if nxt == ring[0]:
            break
        ring.append(nxt); prev, cur = cur, nxt
        if len(ring) > 100000:
            break
    N = len(ring)
    if N < 8:
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    P = np.array([[bm.verts[i].co.x, bm.verts[i].co.y, bm.verts[i].co.z] for i in ring], dtype=np.float64)
    # ① 间距均匀化: 只【拆分长边 + 合并退化短边】(增删顶点, 不拖动已有顶点 → 不拽坏相邻面)
    for _ in range(3):
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        ring_edges = [e for v in ring for e in bm.verts[v].link_edges if len(e.link_faces) == 1]
        seen = set(); re_ = []
        for e in ring_edges:
            k = tuple(sorted((e.verts[0].index, e.verts[1].index)))
            if k not in seen:
                seen.add(k); re_.append(e)
        long_e = [e for e in re_ if (e.verts[0].co - e.verts[1].co).length > RIM_REBUILD_MAX_MM / 1000.0]
        if long_e:
            bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=False)
            bmesh.update_edit_mesh(mesh)
            bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        ring_v = [v for v in bm.verts
                  if (v.co - cv).xz.length < EYE_AREA_R and v.co.y < cv.y + Y_FRONT_M
                  and sum(1 for e in v.link_edges if len(e.link_faces) == 1) == 2]
        if ring_v:
            bmesh.ops.remove_doubles(bm, verts=ring_v, dist=RIM_REBUILD_MIN_MM / 1000.0)
            bmesh.update_edit_mesh(mesh)
            bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        # 重新排序
        nadj = {}
        for v in bm.verts:
            if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
                continue
            nb = [e.other_vert(v).index for e in v.link_edges if len(e.link_faces) == 1]
            if len(nb) == 2:
                nadj[v.index] = nb
        st = [k for k in nadj if len(nadj[k]) == 2]
        if not st:
            break
        ring = [st[0]]; prev, cur = -1, st[0]
        while cur in nadj:
            cand = [n for n in nadj[cur] if n != prev]
            if not cand:
                break
            nxt = cand[0]
            if nxt == ring[0]:
                break
            ring.append(nxt); prev, cur = cur, nxt
            if len(ring) > 100000:
                break
    N = len(ring)
    if N < 8:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"rebuild_ring_arc_length {side}: 环顶点不足({N})")
        return
    P = np.array([[bm.verts[i].co.x, bm.verts[i].co.y, bm.verts[i].co.z] for i in ring], dtype=np.float64)
    # ② 深度 y 按弧长低通(间距已近均匀 → 索引域≈弧长域), 只改 y
    y = P[:, 1].copy()
    y0 = y.copy()
    done = 0
    for _ in range(RIM_REBUILD_PASSES):
        y = (1 - RIM_REBUILD_LAMBDA) * y + RIM_REBUILD_LAMBDA * 0.5 * (np.roll(y, 1) + np.roll(y, -1))
        done += 1
        if np.abs(y - y0).max() > RIM_REBUILD_CAP_MM / 1000.0:
            done -= 1
            break
    lift = float(np.abs(y - y0).max()) * 1000.0
    for k, vi in enumerate(ring):
        c = bm.verts[vi].co
        bm.verts[vi].co = Vector((c.x, float(y[k]), c.z))
    step = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1) * 1000.0
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"rebuild_ring_arc_length {side}: 环 {N} 顶点, 间距[{step.min():.3f},{step.max():.3f}]mm(中位{np.median(step):.3f}), "
          f"深度低通 {done}passes |Δy|max {lift:.3f}mm(上限{RIM_REBUILD_CAP_MM}), XZ 一个字节没动")


def smooth_ring_depth(obj, center, side):
    """v64c: 只平滑 rim 环的【深度 y 剖面】, XZ 严格不动(=手描轮廓形状不变).

    根因(实测 _render_spotL.py + _diag_L_ring.py): L 环 5 个 30~38° 折角全在"下睑靠外眼角"
    一处, 该处表面有 1.2mm 台阶 → 环跨过去时 y 剖面出现台阶 → 3D 转角大; 而 XZ 到轮廓只有
    0.02~0.045mm(切得很准)。表面平滑(0.41mm上限)压不下去, 因为那就是眼睑真实的褶。
    做法: 把环按顺序排好, 只对 y 做沿环的 Laplacian 低通(带位移上限), x/z 一个字节都不动 →
    洞形不变, 环的 3D 走向变光滑。y 只动零点几毫米, 视觉不可见。
    """
    if not RIM_DEPTH_SMOOTH:
        return
    cv = Vector((float(center[0]), float(center[1]), float(center[2])))
    mesh = obj.data
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    nadj = {}
    for v in bm.verts:
        if (v.co - cv).xz.length > EYE_AREA_R or v.co.y > cv.y + Y_FRONT_M:
            continue
        nb = [e.other_vert(v).index for e in v.link_edges if len(e.link_faces) == 1]
        if len(nb) == 2:
            nadj[v.index] = nb
    if not nadj:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"smooth_ring_depth {side}: 未找到环")
        return
    y0 = {vi: bm.verts[vi].co.y for vi in nadj}
    y = dict(y0)
    cap = RIM_DEPTH_CAP_MM / 1000.0
    lam = RIM_DEPTH_LAMBDA
    done = 0
    for _ in range(RIM_DEPTH_PASSES):
        yn = {}
        for vi, nb in nadj.items():
            yn[vi] = (1 - lam) * y[vi] + lam * 0.5 * (y[nb[0]] + y[nb[1]])
        y = yn
        done += 1
        if max(abs(y[vi] - y0[vi]) for vi in y) > cap:
            done -= 1
            break
    for vi in y:
        c = bm.verts[vi].co
        bm.verts[vi].co = Vector((c.x, y[vi], c.z))
    _mv = max(abs(y[vi] - y0[vi]) for vi in y) * 1000.0
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"smooth_ring_depth {side}: 环 {len(y)} 顶点, y 低通 {done}passes, 最大 |Δy| {_mv:.3f}mm (上限 {RIM_DEPTH_CAP_MM}mm), XZ未动")


def make_eye_socket(obj, center, side):
    """开孔: 沿手描眼睑轮廓切出眼洞.
    v62(2026-09-14): 洪泛删面 → 棱柱 boolean EXACT 切割.
      根因: 洪泛删面的洞边界只能落在网格边环上 → 到手描轮廓偏差最大~1mm(网格量化),
            红材质边界因此有~1mm锯齿/尖角. 棱柱侧壁是过轮廓段的竖直平面, 切出的边界必然贴轮廓.。
    旧路径(floodfill, SOCKET_CUT_MODE 切换)保留作A/B与回退."""
    mesh = obj.data
    center = Vector(center)

    # 按当前模型推导全部尺度参数(换头/换眼型自动适配; 替代硬编码 mm)
    try:
        import json as _j
        with open(EYELID_CONTOUR_JSON, encoding="utf-8") as _f:
            _dl = _j.load(_f).get(side)
    except Exception:
        _dl = None
    derive_scale(obj, center, side, _dl)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    
    poly = load_eyelid_contour(side) if USE_EYELID_CONTOUR else None
    if poly is not None and RIM_CONTOUR_SMOOTH:
        poly, _cdev = smooth_contour(poly)
        print(f"make_eye_socket {side}: 轮廓光滑化({RIM_CONTOUR_RESAMPLE}点, 前{RIM_CONTOUR_HARMONICS}次谐波), "
              f"与手描轮廓最大偏差 {_cdev:.3f}mm")
    if poly is not None:
        poly = apply_local_inset(poly, center, side, RIM_LOCAL_INSET)
    cx, cy, cz = center.x, center.y, center.z
    rx, rz = HOLE_RX, HOLE_RZ
    
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    # y限制: cy+20mm(鼓包最深处~-0.10也要删净; 轮廓只覆盖眼区, 不会误删后脑壳)
    y_cut = cy + 0.020
    def inside_poly(fc):
        if fc.y >= y_cut: return False
        if poly is not None:
            return point_in_polygon(fc.x, fc.z, poly)
        return ((fc.x-cx)/rx)**2 + ((fc.z-cz)/rz)**2 <= 1.0

    if SOCKET_CUT_MODE == "boolean" and poly is not None:
        # ================= v62: 棱柱 boolean 切割 =================
        # ① 轮廓内面(切割前统计, 仅供 v43 UV样本映射)
        in_poly = [f for f in bm.faces
                   if (f.calc_center_median() - center).xz.length < EYE_AREA_R
                   and inside_poly(f.calc_center_median())]
        uv_layer_src = bm.loops.layers.uv.active
        samples = []
        if uv_layer_src:
            for f in in_poly:
                for loop in f.loops:
                    co = loop.vert.co
                    uv = loop[uv_layer_src].uv
                    if 0.01 < uv.x < 0.99 and 0.01 < uv.y < 0.99:
                        samples.append((co.x - center.x, co.z - center.z, uv.x, uv.y))
        _EYE_UV_SAMPLES[side] = samples
        print(f"make_eye_socket {side}: captured {len(samples)} eye-region UV samples "
              f"({len(in_poly)} 轮廓内面) for bowl mapping")
        bpy.ops.object.mode_set(mode='OBJECT')
        # ①b v64: 切割前先在 rim 带去噪(修"换角度看 rim 环不直": 环=网格边环, 继承面微噪声)
        denoise_rim_band(obj, center, side, poly)
        # ② boolean 切洞 (返回"新面材质槽"号)
        _cut_slot = cut_hole_by_prism(obj, poly, center, side)
        if SOCKET_EMPTY_INTERIOR:
            # ③a v64(用户方案): 掏空环内 —— 删掉 boolean 切出的坑壁+坑底, 只留 rim 环与空腔.
            #     眼窝形状留到 QR 低模上补; 无需材质分区/UV重映射.
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()
            _cutf = [f for f in bm.faces if f.material_index == _cut_slot]
            if _cutf:
                bmesh.ops.delete(bm, geom=_cutf, context='FACES')
            bmesh.update_edit_mesh(mesh)
            bm = bmesh.from_edit_mesh(mesh)
            bm.verts.ensure_lookup_table()
            _ring_v = [v for v in bm.verts
                       if any(len(e.link_faces) == 1 for e in v.link_edges)
                       and (v.co - center).xz.length < EYE_AREA_R and v.co.y < center.y + Y_FRONT_M]
            _n0 = len(_ring_v)
            if _ring_v:
                bmesh.ops.remove_doubles(bm, verts=_ring_v, dist=RIM_WELD_MM / 1000.0)   # 焊接环上退化小边
            bmesh.update_edit_mesh(mesh)
            bpy.ops.object.mode_set(mode='OBJECT')
            _mnames = [m.name if m else None for m in mesh.materials]
            if "SOCKET_CUT_TMP" in _mnames:
                mesh.materials.pop(index=_mnames.index("SOCKET_CUT_TMP"))
            # 环去刺: ① 先对尖点处【表面】做局部去噪(根因: 表面在那儿有褶/噪点) ② 再对环上残余尖点做环内松弛
            rebuild_rim_band(obj, center, side, poly)   # v85 D2: 整圈 rim 皮肤带重建(替代局部补片)
            remove_ring_folds(obj, center, side)
            relax_surface_at_spikes(obj, center, side)
            relax_ring_spikes(obj, center, side)
            rebuild_ring_arc_length(obj, center, side)
            smooth_ring_depth(obj, center, side)
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(mesh)
            bm.edges.ensure_lookup_table()
            _oe = [e for e in bm.edges if len(e.link_faces) == 1
                   and (e.verts[0].co - center).xz.length < EYE_AREA_R
                   and e.verts[0].co.y < center.y + Y_FRONT_M]
            bpy.ops.object.mode_set(mode='OBJECT')
            print(f"make_eye_socket {side}: boolean掏空环内完成, 删坑面 {len(_cutf)}, "
                  f"rim环顶点 {_n0}→{len(_oe)}")
            bpy.ops.object.mode_set(mode='EDIT')
            return
        # ③b v63: 保留 boolean 切出的眼窝 pit(竖直壁+平底), 按材质槽【精确】识别这些新面 → 打 tag=2.
        #    不再删壁面重建碗: 删壁面后环走不通(实测L环间距45mm/R侧M=5), 且pit的开口边界本来就精确贴轮廓.
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        _tagb = bm.faces.layers.int.get("v44tag_" + side)
        if _tagb is None:
            _tagb = bm.faces.layers.int.new("v44tag_" + side)
        _pit = 0
        for f in bm.faces:
            if f.material_index == _cut_slot:
                f[_tagb] = 2
                f.smooth = True
                _pit += 1
        bmesh.update_edit_mesh(mesh)
        bpy.ops.object.mode_set(mode='OBJECT')
        # 删临时材质槽(材质稍后由 assign_socket_material 按 tag 重设)
        _mnames = [m.name if m else None for m in mesh.materials]
        if "SOCKET_CUT_TMP" in _mnames:
            mesh.materials.pop(index=_mnames.index("SOCKET_CUT_TMP"))
        print(f"make_eye_socket {side}: boolean切出眼窝pit, 标记碗面 {_pit} 面")
        bpy.ops.object.mode_set(mode='EDIT')
    else:
        # ================= 旧路径: 洪泛删面(A/B与回退) =================
        f2f = {}
        for f in bm.faces:
            f2f[f.index] = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                a, b = e.link_faces[0].index, e.link_faces[1].index
                f2f[a].append(b); f2f[b].append(a)
        # 找离眼中心最近的面作种子(必须用3D距离: xz最近会选到后脑勺同x/z的面y=+0.09)
        seed = min(bm.faces, key=lambda f: (f.calc_center_median()-center).length)
        to_delete = set([seed.index])
        stack = [seed.index]
        while stack:
            fi = stack.pop()
            for nb in f2f[fi]:
                if nb in to_delete: continue
                nf = bm.faces[nb]
                if inside_poly(nf.calc_center_median()):
                    to_delete.add(nb)
                    stack.append(nb)
        del_faces = [bm.faces[i] for i in to_delete]
        # v43: 删面前捕获眼区面的顶点级UV样本
        uv_layer_src = bm.loops.layers.uv.active
        samples = []
        if uv_layer_src:
            for f in del_faces:
                for loop in f.loops:
                    co = loop.vert.co
                    uv = loop[uv_layer_src].uv
                    if 0.01 < uv.x < 0.99 and 0.01 < uv.y < 0.99:
                        samples.append((co.x - center.x, co.z - center.z, uv.x, uv.y))
        _EYE_UV_SAMPLES[side] = samples
        print(f"make_eye_socket {side}: captured {len(samples)} eye-region UV samples for bowl mapping")
        bmesh.ops.delete(bm, geom=del_faces, context='FACES')
        bmesh.update_edit_mesh(mesh)
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"make_eye_socket {side}: flood-fill deleted {len(del_faces)} faces (single connected patch)")
    print(f"make_eye_socket {side}: push-in removed (凹陷由碗负责)")
    
    # 局部焊接重复顶点(不动法线, 历史教训: 全局Shift+N会翻过洞边缘)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    # v62: boolean模式下threshold缩小到20µm(boolean EXACT产物本就无重复顶点, 只需并真重合点);
    #   floodfill模式的0.1mm会把切出来的密集边界顶点并掉.
    bpy.ops.mesh.remove_doubles(threshold=(0.00002 if SOCKET_CUT_MODE == "boolean" else 0.0001))
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: cleanup done (local weld only, no global recalc)")
    
    # 2026-08-07 v13: 溶解口沿碎片面(<0.5mm²的sliver, 原有皮肤碎片, 法线乱->锯齿尖刺根因).
    # 只溶解严格内部面(所有边恰2面), 绝不碰边界环上的面(防开洞). ad-hoc验证抓到此缺陷.
    # 2026-08-13 v23: 加z上限<1.678(与轮廓z上沿一致), 防sliver溶解触及眉毛z>1.68→UV错乱.
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    slivers = [] if SOCKET_CUT_MODE == "boolean" else [f for f in bm.faces
               if f.calc_area() < 0.5e-6
               and (f.calc_center_median()-center).xz.length < 0.015
               and f.calc_center_median().z < 1.678
               and all(len(e.link_faces)==2 for e in f.edges)]
    if slivers:
        _dis = bmesh.ops.dissolve_faces(bm, faces=slivers)
        bmesh.update_edit_mesh(mesh)
        # 2026-08-13 v24: 消除溶解产生的ngon(多边面→三角化, 防止法线异常/破面/布线乱)
        # v59d根因修复: 旧代码全局扫bm.faces三角化【所有】ngon — L/R处理顺序下,
        #   socket R会把cup L已建好的碗底ngon盖(84边)和rim合并ngon全部打碎成三角
        #   (实测L碗面232三角面 vs R 0). 修: 只三角化本次dissolve的产物(region).
        _region = [f for f in _dis.get("region", []) if f.is_valid]
        ngons = [f for f in _region if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
            bmesh.update_edit_mesh(mesh)
            print(f"  triangulated {len(ngons)} ngons after dissolve (region-local)")
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: dissolved {len(slivers)} sliver faces")


def seal_socket_bottom(obj, center, side):
    """封碗底: 在眼窝开口后方生成一个凹陷的封闭碗状曲面, 防止从洞口看穿到后脑内部.
    
    原理: 找到开口边界环(开放边), 在碗底中心加一个点, 用三角扇把边界环连到碗底.
    碗底深度 = SOCKET_DEPTH * CUP_DEPTH_RATIO, 保证眼球放进去后有封闭背景.
    """
    mesh = obj.data
    center = Vector(center)
    cup_depth = SOCKET_DEPTH * CUP_DEPTH_RATIO   # 碗底比压凹更深一点
    rim_y = center.y                              # 开口平面的 y (脸表面)
    bottom_y = rim_y + cup_depth                  # +Y 朝头内
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # 找开口边界环: 只有1个面相邻的边(开放边), 且靠近眼窝中心
    boundary_verts = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            mx = (e.verts[0].co.x + e.verts[1].co.x) / 2
            mz = (e.verts[0].co.z + e.verts[1].co.z) / 2
            # 边界边中点要在椭圆附近(1.0~1.6倍半径), 才是眼窝的洞边
            dx = (mx - center.x) / HOLE_RX
            dz = (mz - center.z) / HOLE_RZ
            r2 = dx*dx + dz*dz
            if 0.6 < r2 < 2.6 and abs((e.verts[0].co.y + e.verts[1].co.y)/2 - rim_y) < 0.03:
                boundary_verts.add(e.verts[0])
                boundary_verts.add(e.verts[1])
    
    if len(boundary_verts) < 3:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"seal_socket_bottom {side}: WARNING only {len(boundary_verts)} boundary verts, skip")
        return
    
    # 把边界顶点按绕中心的角度排序, 形成有序环
    import math
    def ang(v):
        return math.atan2(v.co.z - center.z, v.co.x - center.x)
    ring = sorted(boundary_verts, key=ang)
    
    # 碗底中心点
    bottom_vert = bm.verts.new((center.x, bottom_y, center.z))
    
    # 三角扇连接: 环上相邻两点 + 碗底中心
    # 法线方向: 要让碗内壁朝外(朝眼球/朝-Y), 绕序需与开口面一致
    new_faces = []
    n = len(ring)
    for i in range(n):
        v1 = ring[i]
        v2 = ring[(i+1) % n]
        try:
            f = bm.faces.new((v1, v2, bottom_vert))
            new_faces.append(f)
        except ValueError:
            pass  # 面已存在
    
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"seal_socket_bottom {side}: ring={n} verts, created {len(new_faces)} fan faces, bottom_y={bottom_y:.4f}")


def make_eye_cup(obj, center, side):
    """眼窝封底: 边界环内收几圈 + 极点三角扇封底.
    用户明确: 内部是个坑就行(眼球会挡), 重点是平滑封闭无破面.
    2026-08-07重写: 旧版ngon封底翘曲出放射扇条纹+孤岛残留锯齿.
    本版: ①删眼区孤岛 ②3圈内收 ③极点扇封底 ④smooth shading."""
    import math
    from collections import defaultdict
    mesh = obj.data
    center = Vector(center)
    # v60(2026-09-14): 碗深按眼球几何反推(球心+球半径+间隙, 见 eye_socket_config 推导),
    # 替代固定 CUP_DEPTH=15mm —— 旧15mm碗底仍在脸面基准之前, 眼球后极还戳穿碗底10.7mm.
    max_depth = SOCKET_CUP_DEPTH
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    # v44: per-side int tag层. 最先创建, 新面创建时立即打tag(倒角带=1/碗=2).
    # 教训: 事后回头打tag会ReferenceError: BMFace removed(wrapper失效).
    # per-side命名: R眼pass不会把L眼已tag面误认成本侧新面(避免用R查找表覆盖L眼UV).
    tag_l = bm.faces.layers.int.get("v44tag_" + side)
    if tag_l is None:
        tag_l = bm.faces.layers.int.new("v44tag_" + side)
    
    def in_zone(co):
        return (co.x-center.x)**2 + (co.z-center.z)**2 < 0.022**2
    
    # ---- 0. 删眼区孤岛: 与主体断开的碎面片(删面残留) ----
    # 建邻接表, 从远离眼区的顶点BFS标记主体连通分量, 眼区内不连通的面=孤岛
    v2f = defaultdict(list)
    for f in bm.faces:
        for v in f.verts:
            v2f[v.index].append(f)
    # 种子: 眼区外、朝脸前的顶点
    seeds = [v.index for v in bm.verts if abs(v.co.x-center.x)>0.030 and abs(v.co.z-center.z)<0.060 and v.co.y<0.02]
    connected = set()
    stack = list(seeds)
    while stack:
        vi = stack.pop()
        if vi in connected: continue
        connected.add(vi)
        for f in v2f[vi]:
            for v in f.verts:
                if v.index not in connected:
                    stack.append(v.index)
    island_faces = [f for f in bm.faces if any(v.index not in connected for v in f.verts) and in_zone(f.calc_center_median())]
    if island_faces:
        bmesh.ops.delete(bm, geom=island_faces, context='FACES')
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
    print(f"make_eye_cup {side}: removed {len(island_faces)} island faces")
    
    # ---- 1. 找所有开放边环, 取最大的 = 眼窝开口边界 ----
    # 2026-08-07 v5根因: 角度排序(atan2)破坏拓扑顺序, quad用跨越新边不共享原边界边
    # -> 原边界边悬空成锯齿裂口(实测封碗后冒出5个开放环). 必须用拓扑行走顺序.
    open_edges = [e for e in bm.edges if len(e.link_faces)==1 and in_zone(e.verts[0].co)]
    adj = defaultdict(list)
    for e in open_edges:
        adj[e.verts[0].index].append(e.verts[1].index)
        adj[e.verts[1].index].append(e.verts[0].index)
    rings = []
    visited_v = set()
    for start in list(adj.keys()):
        if start in visited_v or len(adj[start]) != 2: continue
        ring = [start]; visited_v.add(start)
        prev, cur = -1, start
        closed = False
        for _ in range(10000):
            nxt = None
            for n in adj[cur]:
                if n == prev: continue
                if n == start:
                    closed = True; break
                if n not in visited_v:
                    nxt = n; break
            if closed or nxt is None: break
            ring.append(nxt); visited_v.add(nxt)
            prev, cur = cur, nxt
        if closed and len(ring) >= 3:
            rings.append(ring)
    if not rings:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"make_eye_cup {side}: WARNING no closed boundary ring, skip")
        return
    ring_idx = max(rings, key=len)
    ring0 = [bm.verts[i] for i in ring_idx]  # 拓扑行走顺序(与网格边界一致, 不排序!)
    M = len(ring0)

    def _rewalk_ring():
        """重走开放边环, 返回(BMVert列表, M) 或 (None,0). 焊/删顶点后索引失效必须重走."""
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        _oe = [e for e in bm.edges if len(e.link_faces)==1 and in_zone(e.verts[0].co)]
        _adj = defaultdict(list)
        for e in _oe:
            _adj[e.verts[0].index].append(e.verts[1].index)
            _adj[e.verts[1].index].append(e.verts[0].index)
        _rings = []; _vis = set()
        for start in list(_adj.keys()):
            if start in _vis or len(_adj[start]) != 2: continue
            ring = [start]; _vis.add(start)
            prev, cur = -1, start; closed = False
            for _ in range(10000):
                nxt = None
                for n in _adj[cur]:
                    if n == prev: continue
                    if n == start: closed = True; break
                    if n not in _vis: nxt = n; break
                if closed or nxt is None: break
                ring.append(nxt); _vis.add(nxt)
                prev, cur = cur, nxt
            if closed and len(ring) >= 3: _rings.append(ring)
        if not _rings: return None, 0
        _ri = max(_rings, key=len)
        return [bm.verts[i] for i in _ri], len(_ri)
    
    # ---- 1.5 v59 rim重构(2026-09-11): 松弛(恢复) + 焊退化边 + sliver保拓扑 + ngon碗底 ----
    # 实测定罪链(_diag_rim/_diag_ring/_spike_*/_baseline_cmp, 全部数字可复现):
    #   • 基线L前视转角XZ仅5.93° — 平滑全靠旧松弛×12(v59f曾误判其"形同虚设"而移除 → 恶化到68°/max179°, 恢复);
    #   • 基线R的真缺陷=顶点爆炸104(vs L 84)+转角XZ 137°/max138°: 触rim的sliver溶解→ngon→三角化改道rim;
    #   • 旧"径向投影"形同虚设(只动6/84、8/76个顶点) → 删除;
    #   • XZ投影到曲线方案否决: 82顶点投72段折线→弧长非单调→转角飙180°尖刺(v59c实测);
    #   • 切割类方案全否决: knife_project(headless 0切割边)/boolean(非流形被拒)/顶点墙洪泛(泄漏删光193万面)/
    #     测地线补全(自交)/等距重排(位移15.9mm)/全量snap到曲线(y位移7.3mm拉坑);
    #   • y跨度16mm≠伪影: 手描曲线是眼睑缘(y-105~-111), 边界环是窝底切口(y达-115.6), y本就不同, 双层竖边=0.
    # ✅ v59定案(只修真缺陷, 位移有界):
    #   ① 3D Laplacian松弛×12 w=0.3(恢复v42配方, 磨zigzag保杏仁形);
    #   ② 焊退化小边<0.3mm(松弛把R的0.126mm近重合顶点压成重合 → 必须焊, 合法边≥0.4mm不误焊);
    #   ③ 触rim的sliver只翻法线不溶解(根治R侧104顶点爆炸, v59b实测R保持76 ✓);
    #   ④ 碗底单极点→单ngon盖(消中心黑洞+放射扇, v59b实测极点=0 ✓).
    #   删除: 旧径向投影(无效). 左右同一程序化流程, 无硬编码坐标.
    import json as _json
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as _f:
        _dd = _json.load(_f)
    _rim_pts = np.array([[r[0]-center.x, r[2]-center.z]
                         for r in _dd[side]["rim_3d"] if r is not None], dtype=np.float64)
    _Nc = len(_rim_pts)

    # ① 3D Laplacian松弛×12 (v42验证过的配方, w=0.3) — 恢复!
    #   v59f教训(基线对比实测): 曾误判松弛"形同虚设"而移除 → L转角XZ从5.93°恶化到68°/max179°.
    #   基线L前视平滑全靠它(把边界环沿曲线的zigzag磨平); 周长119→88mm的"收缩"实为磨锯齿的正常代价
    #   (基线周长88mm = 平滑杏仁形的真实周长, 手描曲线周长78.8mm, 差值=环贴曲线的深度起伏).
    #   v59新增价值: ④sliver翻法线保住R侧拓扑(基线R被溶解-三角化撑到104顶点/137°转角), 松弛作用在干净环上.
    # v62: boolean切出的边界已精确贴轮廓(偏差中位0.0000mm) → 松弛会把边界推离轮廓, 必须跳过;
    #   floodfill旧路径的边界是网格锯齿边, 仍需松弛×12磨平(v59定案).
    _RELAX_N = 0 if SOCKET_CUT_MODE == "boolean" else 12
    for _ in range(_RELAX_N):
        new_pos = {}
        for i, v in enumerate(ring0):
            a = ring0[(i-1)%M].co; b = ring0[(i+1)%M].co
            w = 0.3
            new_pos[v.index] = v.co*(1-w) + (a+b)*0.5*w
        for v in ring0:
            v.co = new_pos[v.index]

    # ② 焊接退化小边(<0.3mm). 松弛把锯齿磨平时可能把近重合顶点(R基线min0.126mm)压到重合 →
    #   退化边/死折/碗面首环退化quad. 合法最短边(松弛后)≥0.4mm > 0.3mm阈值, 不误焊.
    _nweld = 0
    for _wr in range(12):
        _pair = None
        for _i in range(M):
            if (ring0[_i].co - ring0[(_i+1) % M].co).length < 0.0003:
                _pair = (ring0[_i], ring0[(_i+1) % M]); break
        if _pair is None:
            break
        _a, _b = _pair
        _a.co = (_a.co + _b.co) / 2
        bmesh.ops.remove_doubles(bm, verts=[_a, _b], dist=0.00035)
        bmesh.update_edit_mesh(mesh)
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        tag_l = bm.faces.layers.int.get("v44tag_" + side) or tag_l
        ring0, M = _rewalk_ring()
        _nweld += 1
        if ring0 is None:
            print(f"  !! v59② 焊边后环丢失(轮{_wr+1}), 中止")
            break
    print(f"  v59② 焊接退化边: {_nweld}次 → M={M}")
    if ring0 is None or M < 8:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"make_eye_cup {side}: !! v59重构后环异常(M={M}), skip")
        return
    # 自检: 最短边/转角/偏离曲线(独立于修复步骤的量, 防自证)
    _P3w = np.array([[v.co.x, v.co.y, v.co.z] for v in ring0])
    _minseg = float(np.min(np.linalg.norm(np.roll(_P3w, -1, axis=0) - _P3w, axis=1)))
    print(f"  v59最终: 最短边={_minseg*1000:.3f}mm")
    rim_y = sum(v.co.y for v in ring0) / M
    # 验证: 转角/间距/偏离曲线
    _post = np.array([[v.co.x-center.x, v.co.z-center.z] for v in ring0])
    _d2v = np.linalg.norm(_post[:,None,:]-_rim_pts[None,:,:], axis=2).min(axis=1)
    _P3w = np.array([[v.co.x, v.co.y, v.co.z] for v in ring0])
    _sp = np.linalg.norm(np.roll(_P3w,-1,axis=0)-_P3w, axis=1)*1000
    _d0 = _P3w-np.roll(_P3w,1,axis=0); _d1 = np.roll(_P3w,-1,axis=0)-_P3w
    _n0 = _d0/(np.linalg.norm(_d0,axis=1,keepdims=True)+1e-12); _n1 = _d1/(np.linalg.norm(_d1,axis=1,keepdims=True)+1e-12)
    _turn = np.degrees(np.arccos(np.clip((_n0*_n1).sum(axis=1),-1,1)))
    print(f"make_eye_cup {side}: boundary ring M={M} (of {len(rings)} rings), v59重构后 "
          f"XZ偏离曲线 max={_d2v.max()*1000:.3f}mm 转角mean={_turn.mean():.1f}°/max={_turn.max():.1f}° "
          f"间距[{_sp.min():.2f},{_sp.max():.2f}]mm")
    _rmm = [np.linalg.norm(p)*1000 for p in _post]
    print(f"  rim半径: [{min(_rmm):.1f},{max(_rmm):.1f}]mm avg={sum(_rmm)/M:.1f}mm")
    
    # ---- 1.55 UV捕获: 必须在创建倒角带/碗面之前! ----
    # v31根因修复: 倒角带创建后ring0顶点多了新loop(chamfer loop, 默认UV=(0,0)),
    # link_loops[0]可能返回chamfer loop → 取到(0,0). 必须在倒角带创建前从皮肤loop捕获.
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
    ring0_uv = {}
    for v in ring0:
        for loop in v.link_loops:
            ring0_uv[v.index] = loop[uv_layer].uv.copy()
            break
    avg_uv = sum((uv for uv in ring0_uv.values()), Vector((0.0, 0.0))) / max(len(ring0_uv), 1)
    
    # ---- 1.6+2. 合并倒角带+碗面(消除ring1分界线/M形环线) ----
    # v46i: 从ring0直接到碗底, 中间无ring1分界线. 倒角带和碗面合并为一块.
    # 根因: 原设计倒角带(8条带)和碗面(16环)分开创建, 在ring1处相接→M形环线.
    # 修复: 从ring0开始, 用单一曲线(宽度W+深度D→收缩到10%)直接到碗底,
    #       中间无分界线. 环数=F+NR, 前F环是倒角(宽度W), 后NR环是碗面(收缩到10%).
    F = CHAMFER_FILLET_RINGS   # 倒角环数(不含ring0)
    # 眼窝平均半径 = (宽+高)/4
    import json as _json2
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as _f2:
        _cd = _json2.load(_f2)
    _w_mm = _cd[side]["width_mm"]; _h_mm = _cd[side]["height_mm"]
    _avg_radius = (_w_mm + _h_mm) / 4.0 / 1000.0  # 米
    W = min(_avg_radius * CHAMFER_WIDTH_RATIO, 0.006)   # 倒角宽度, 上限6mm
    D = W * CHAMFER_DEPTH_RATIO                          # 倒角深度 = 宽度的50%
    # v47方案A: 不倒角 → W=D=F=0, 碗面从rim直接单一smoothstep收缩下沉
    if SOCKET_VARIANT == "no_chamfer":
        W = 0.0; D = 0.0; F = 0
    # v48: 内圆角平滑接缝 → 只内收+下沉(绝不外扩→几何上不可能产生M形凸脊),
    # quintic q在t=0零斜率起步, 与皮肤表面切线连续, 接缝无硬边.
    # 符号注意: rad_dirs指向眼中心, W正值=内收(原倒角自检证实), 负值会外扩!
    elif SOCKET_VARIANT == "inward_fillet":
        W = SOCKET_FILLET_INWARD    # 正值=径向内收1.2mm
        D = SOCKET_FILLET_DEPTH
        F = SOCKET_FILLET_RINGS
    print(f"  倒角参数[{SOCKET_VARIANT}]: 眼窝{_w_mm:.1f}x{_h_mm:.1f}mm avg半径{_avg_radius*1000:.1f}mm → 倒角宽{W*1000:.2f}mm 深{D*1000:.2f}mm F={F}")
    
    rad_dirs = []
    for v in ring0:
        rad = Vector((center.x - v.co.x, 0, center.z - v.co.z))
        rad_dirs.append(rad / rad.length if rad.length > 1e-9 else Vector((0,0,0)))
    
    # 合并环: 前F环倒角 + 后NR环碗面, 共F+NR环
    NR = 16  # 碗面环数
    all_rings = [list(ring0)]  # 第0环=ring0
    for k in range(1, F + NR + 1):  # k=1..F+NR
        if k <= F:
            # 倒角部分: 宽度W, 深度D, quintic smoothstep
            t = k / (F + 1)
            q = t*t*t*(t*(6.0*t - 15.0) + 10.0)
            depth = D * q
            radial = W * q
            scale = 1.0  # 不收缩, 只下沉
        else:
            # 碗面部分: 从倒角末端开始, 收缩到25%.
            # v46j教训: 收缩到10%时末环半径≈1.2mm, 84顶点间距仅0.09mm <
            # remove_doubles阈值0.1mm → 碗底正常顶点被焊坍缩(84→55).
            # 收缩到25%: 末环半径≈3mm, 间距0.22mm>0.1mm安全, 碗底也不需要更高密度.
            t = (k - F) / NR
            s = t*t*(3 - 2*t)  # smoothstep
            scale = 1.0 - 0.75 * s  # 收缩到25%
            depth = D + (rim_y + max_depth - D - rim_y) * s  # 从倒角深度继续下沉
            radial = 0  # 不再外扩, 只收缩
        row = []
        for i in range(M):
            base = ring0[i].co
            # 先倒角(外扩+下沉), 再收缩(径向收缩)
            if k <= F:
                pos = base + rad_dirs[i] * radial + Vector((0, depth, 0))
            else:
                # 倒角末端位置
                chamfer_end = base + rad_dirs[i] * W + Vector((0, D, 0))
                # 从倒角末端收缩
                pos = center + (chamfer_end - center) * scale + Vector((0, depth - D, 0))
            row.append(bm.verts.new(pos))
        all_rings.append(row)
    
    # 创建面: 相邻环quad, 全部打tag=2(碗面, 不再区分倒角带)
    new_faces = []
    for j in range(len(all_rings)-1):
        for i in range(M):
            i2=(i+1)%M
            a=all_rings[j][i]; b=all_rings[j][i2]; c=all_rings[j+1][i2]; d=all_rings[j+1][i]
            try:
                _nf = bm.faces.new((a,d,c,b))
                _nf.smooth = True
                _nf[tag_l] = 2
                new_faces.append(_nf)
            except ValueError: pass
    
    # 碗底: v59(2026-09-11) 单极点放射扇 → 单个ngon平面盖.
    # 根因(用户GUI截图): 极点扇=中心黑洞+放射布线; 且极点处三角面积0.02mm²级易触发下游误判.
    # 末环已收缩到25%(半径≈3mm), 直接用ngon封顶: 高模线框=一个多边形, 无放射线.
    # 眼球放置后完全遮挡; QR/FBX内部会自行三角化, 不需要高模保持扇形.
    last = all_rings[-1]
    try:
        _cap = bm.faces.new(tuple(last))
        _cap[tag_l] = 2
        _cap.smooth = False        # 平面盖不参与smooth shading(平面无需)
        new_faces.append(_cap)
        cap_face = _cap
        print(f"  v59碗底: 单ngon盖 {len(last)}边 (替代单极点{M}三角放射扇)")
    except ValueError as _e:
        # 兜底: ngon创建失败(自交等)则回退极点扇 — 不应发生, 发生即报告
        print(f"  !! v59碗底ngon失败({_e}), 回退极点扇")
        pole = bm.verts.new((center.x, rim_y + max_depth, center.z))
        for i in range(M):
            try:
                _nf = bm.faces.new((last[(i+1)%M], last[i], pole))
                _nf[tag_l] = 2
                new_faces.append(_nf)
            except ValueError: pass
    
    # 实测倒角宽度自检(前F环的径向内收量)
    _span = []
    for i in range(M):
        _r0 = (ring0[i].co - center).xz.length
        _r1 = (all_rings[F][i].co - center).xz.length  # 倒角末端环
        _span.append((_r0 - _r1) * 1000)
    print(f"  合并环: {len(new_faces)} faces ({F+NR} rings x {M}), "
          f"倒角宽度 min={min(_span):.2f}mm max={max(_span):.2f}mm avg={sum(_span)/len(_span):.2f}mm")

    # ---- v47方案B: Laplacian松弛眼窝内部环, 磨圆倒角凸脊(M线) ----
    # ring0(rim,已缝合皮肤)和碗底极点锁住不动, 其余环顶点向邻居均值靠拢.
    # Jacobi式(每轮用旧坐标算delta)避免不对称漂移.
    # 教训: 新建顶点后v.index未ensure_lookup_table()会过期/冲突, 锁定必须用对象身份id().
    if SOCKET_VARIANT == "chamfer_relax" and SOCKET_RELAX_PASSES > 0:
        _interior = [v for ring in all_rings[1:] for v in ring]
        _locked = set(id(v) for v in ring0)
        _locked.add(id(cap_face))
        def _max_r():
            return max((v.co - center).xz.length for v in _interior) * 1000
        _r_before = _max_r()
        for _p in range(SOCKET_RELAX_PASSES):
            _deltas = {}
            for v in _interior:
                if id(v) in _locked:
                    continue
                nbrs = [e.other_vert(v) for e in v.link_edges]
                if not nbrs:
                    continue
                avg = sum((n.co for n in nbrs), Vector((0.0, 0.0, 0.0))) / len(nbrs)
                _deltas[id(v)] = (avg - v.co) * SOCKET_RELAX_LAMBDA
            _moved = 0
            for v in _interior:
                d = _deltas.get(id(v))
                if d is not None and d.length > 1e-9:
                    v.co += d
                    _moved += 1
            if _p == 0 or _p == SOCKET_RELAX_PASSES - 1:
                print(f"    松弛轮{_p}: 移动{_moved}/{len(_interior)}顶点, 最大半径{_max_r():.3f}mm")
        _r_after = _max_r()
        print(f"  v47松弛: {SOCKET_RELAX_PASSES}轮 λ={SOCKET_RELAX_LAMBDA} "
              f"{len(_interior)}内部顶点, 最大半径{_r_before:.2f}→{_r_after:.2f}mm")
    
    # v44: 拓扑标记已在面创建时完成(倒角带=1/碗=2, per-side层).
    # v43b根因: ring0半径随角度3.9~13.8mm变化(杏仁), 固定12/15/18mm径向分段错位 →
    #   ①上下睑ring0<12mm处原始皮肤被套眼睛贴图(睫毛渗到眼睑→开口显宽圆/拉伸带)
    #   ②眼角倒角带12~18mm被写常数UV(眼角贴片)
    # 修复: 只给tag面分配眼睛贴图UV, 原始皮肤UV一律不动(见下方v44 UV段).
    
    # smooth shading(与皮肤一致, 消棱面)
    for f in new_faces:
        f.smooth = True
    # v46i: 合并后无chamfer_faces, 不再单独平滑
    bmesh.update_edit_mesh(mesh)
    
    # v46i: 用坐标快照保存ring0多边形(供后续法线处理用)
    ring0_coords = [tuple(v.co) for v in ring0]
    
    # 2026-08-07 v14: 溶解封碗后才变内部的反向sliver(口沿皮肤碎片, 删面时在边界上没敢溶).
    # 封碗后它们变内部, 0.1um²且法线朝+Y(反), 是锯齿尖刺根因. 只溶严格内部面.
    # 2026-08-13 v23: 加z上限<1.678, 同make_eye_socket, 防触及眉毛区.
    # 2026-08-13 v32根因修复: 加y上限<rim_y+1mm! 碗底极点三角扇面积极小(0.0001mm2级)
    # 且满足原判据 → 被误溶 → 碗底出现开放边+非流形边(实测L眼1开放边+2非流形边).
    # v59(2026-09-11): 触ring0的sliver【只翻法线不溶解】!
    #   根因(实测): 溶解触rim的sliver→邻面合并成ngon→三角化重铺→材质边界改道,
    #   R侧rim从76顶点撑到104、转角飙出117.6°死折(v58c用户所见锯齿的几何源头之一).
    #   翻法线同样消黑刺(反向→朝前), 零拓扑改动, v59曲线吸附的成果不被破坏.
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    _rim_vids = set(id(v) for v in ring0)
    flipped_slivers = [f for f in bm.faces
                       if f.calc_area() < 0.5e-6 and f.normal.y > 0.3
                       and (f.calc_center_median()-center).xz.length < 0.015
                       and f.calc_center_median().z < 1.678
                       and f.calc_center_median().y < rim_y + 0.001
                       and all(len(e.link_faces)==2 for e in f.edges)]
    rim_slivers = [f for f in flipped_slivers if any(id(v) in _rim_vids for v in f.verts)]
    _rimset = set(id(f) for f in rim_slivers)
    # v62: boolean模式下不溶解内部sliver — 溶解会把切出来的密集边界/碗面细面吞掉(实测R侧环被溶到M=3).
    inner_slivers = [] if SOCKET_CUT_MODE == "boolean" else [f for f in flipped_slivers if id(f) not in _rimset]
    if rim_slivers:
        bmesh.ops.reverse_faces(bm, faces=rim_slivers)
        bm.normal_update()
        bmesh.update_edit_mesh(mesh)
    if inner_slivers:
        _dis2 = bmesh.ops.dissolve_faces(bm, faces=inner_slivers)
        bmesh.update_edit_mesh(mesh)
        # 2026-08-13 v24: 消除溶解产生的ngon
        # v59d根因修复(同make_eye_socket): 旧代码全局扫所有ngon三角化, 但只按【本侧】tag层排除碗底盖 →
        #   cup R 的pass里 L 的ngon盖带的是 v44tag_L==2 / v44tag_R==0, 不被排除 → L碗底盖被打碎成三角
        #   (实测L碗面232三角, 其中72个在碗底深度). 修: 只三角化本次dissolve产物(region), 天然不碰别侧/碗底.
        _region2 = [f for f in _dis2.get("region", []) if f.is_valid]
        ngons = [f for f in _region2 if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
            bmesh.update_edit_mesh(mesh)
            print(f"  triangulated {len(ngons)} ngons after flipped_sliver dissolve (region-local)")
    print(f"make_eye_cup {side}: rim slivers翻法线={len(rim_slivers)} 内部slivers溶解={len(inner_slivers)}")
    
    # ---- 3. 拐角过渡由挤出缓冲环完成(v30), 废弃subdivide/bevel ----

    # ---- 4. 法线校正: recalc_face_normals 拓扑传递(替代手动reverse_faces) ----
    # 纯绕序测试证实: 创建绕序不对(L仅19%朝眼球), recalc绝对必要.
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    # v32: 用坐标最近邻重建ring0(索引在dissolve/mode切换后会重排失效)
    bm.verts.ensure_lookup_table()
    all_v = list(bm.verts)
    ring0_rebuilt = []
    for coord in ring0_coords:
        cv = Vector(coord)
        best = min(all_v, key=lambda v: (v.co - cv).length_squared)
        ring0_rebuilt.append(best)
    # 碗面 = 碗区内的面+倒角带(只限前脸 y<0, 排除后脑勺), xz<0.021覆盖全部
    bowl_zone = [f for f in bm.faces
                 if (f.calc_center_median() - center).xz.length < 0.021
                 and f.calc_center_median().y < 0]
    # 参考皮肤面 = ring0外侧相邻的皮肤三角面(法线绝对正确)
    ref_faces = []
    for v in ring0_rebuilt:
        for f in v.link_faces:
            if len(f.verts) == 3 and f not in ref_faces:
                ref_faces.append(f)
    ref_unique = [f for f in ref_faces if f not in bowl_zone]
    # v38: 禁用recalc, 它会强制碗面+皮肤同向, 但碗面应朝-Y而皮肤应朝外, 二者不同.
    # recalc之后几何兜底再翻, 但recalc又把面翻回去. 直接禁用recalc, 只用几何兜底.
    _SKIP_RECALC = True
    if bowl_zone and ref_unique and not _SKIP_RECALC:
        try:
            bmesh.ops.recalc_face_normals(bm, faces=bowl_zone + ref_unique)
            bmesh.update_edit_mesh(mesh)
            print(f"  recalc_face_normals: {len(bowl_zone)} bowl + {len(ref_unique)} ref faces")
        except Exception as e:
            print(f"  recalc_face_normals failed: {e}")
    elif _SKIP_RECALC:
        print("  recalc_face_normals: SKIPPED (v38, geometric only)")

    # ---- 5. 几何朝向保证 v38: 眼窝所有面法线必须朝头前(-Y) ----
    # v38根因: "朝眼球"判据错误 + normal_flip在update_edit_mesh时丢失(和v36 reverse_faces一样).
    # 证据: xz13-20mm大量normal.y>0.3(朝头内)面=用户看到的黑色/反向面.
    # 正确几何: 眼窝是凹陷, 从前面看进去, 所有可见面(碗内壁+倒角带)法线都应朝-Y(头前/观察者).
    # 修复: 用bmesh.ops.reverse_faces(标准算子, 同时改绕序+缓存, update_edit_mesh不丢失).
    # 判据: normal.y>0(朝头内=反向).
    flipped_geo = 0
    to_flip = []
    for f in bm.faces:
        fc = f.calc_center_median()
        # v45: rim扩大后(avg10.9mm) xz半径需从0.021扩到0.025, 覆盖碗外缘翻转面
        if center.y < fc.y < center.y + 0.02 and (fc - center).xz.length < 0.025:
            if f.normal.y > 0:
                to_flip.append(f)
    if to_flip:
        bmesh.ops.reverse_faces(bm, faces=to_flip)
        bm.normal_update()
        flipped_geo = len(to_flip)
    bmesh.update_edit_mesh(mesh)
    # v38: 立即自检确认翻转生效
    _still_wrong = sum(1 for f in bm.faces
                       if center.y < f.calc_center_median().y < center.y + 0.02
                       and (f.calc_center_median() - center).xz.length < 0.025
                       and f.normal.y > 0)
    print(f"  geometric orientation: reversed {flipped_geo} bowl faces to face -Y, still wrong={_still_wrong}")

    # v39: UV分配(所有几何操作完成后, 防止被update_edit_mesh覆盖)
    # 碗面全部用avg_uv(均匀皮肤色), 倒角带ring0继承皮肤UV, 内部环用avg_uv.
    # v39修复: 眼窝区UV与皮肤UV连续过渡, 避免交界处断裂.
    # 关键: 重新从mesh创建bmesh, 确保包含所有顶点.
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
    # 收集眼窝开口边缘的皮肤UV(用于连续过渡)
    # v42b: 取样窗口改为"下眼睑皮肤区"(dz<0下侧), 避开上眼睑贴图深色眼妆区.
    #       原窗口(xz15-20mm整圈)穿过上眼睑→中位数UV落进眼线/眼影深色像素(亮度0.15-0.35)→
    #       碗面采样成深棕色(用户截图红箭头指的下眼睑深色斑块). 下眼睑皮肤区实测亮度0.48.
    #       同时过滤深色UV样本(亮度<0.40视为眼妆区丢弃).
    tex_img = None
    for _m in obj.data.materials:
        if _m and _m.use_nodes:
            for _n in _m.node_tree.nodes:
                if _n.type == 'TEX_IMAGE' and _n.image:
                    tex_img = _n.image
    _tex_px = tex_img.pixels[:] if tex_img else None
    _TW, _TH = tex_img.size if tex_img else (0, 0)
    def _uv_bright(u, v):
        if not _tex_px: return 1.0
        _x = min(max(int(u*_TW), 0), _TW-1); _y = min(max(int(v*_TH), 0), _TH-1)
        _i = (_y*_TW + _x)*4
        return (_tex_px[_i] + _tex_px[_i+1] + _tex_px[_i+2]) / 3
    skin_uvs = []
    for v in bm.verts:
        dx = v.co.x - center.x; dz = v.co.z - center.z
        dxz = math.sqrt(dx*dx + dz*dz)
        # v42b: 下眼睑皮肤区(dz<0下侧), 碗外18-30mm, 脸部前缘
        if dz < -0.008 and 0.6 * EYE_AREA_R < dxz < EYE_AREA_R and v.co.y < center.y:
            for loop in v.link_loops:
                uv = loop[uv_layer].uv
                if 0.01 < uv.x < 0.99 and 0.01 < uv.y < 0.99:
                    # v42b: 丢弃深色样本(眼妆/眼线区)
                    if _uv_bright(uv.x, uv.y) > 0.40:
                        skin_uvs.append((v.co.copy(), uv.copy()))
                break
    if skin_uvs:
        # 计算avg_uv(中位数)
        us = sorted([uv.x for co, uv in skin_uvs])
        vs = sorted([uv.y for co, uv in skin_uvs])
        avg_u = us[len(us)//2]
        avg_v = vs[len(vs)//2]
    else:
        avg_u, avg_v = 0.5, 0.5
    # v40: 先修复 UV=(0,0) 残留 loop (输入模型眼球残留面片, 采样贴图亮角→白弧带)
    zero_fixed = 0
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz < 0.025 and abs(fc.y - center.y) < 0.015:
            for loop in f.loops:
                if loop[uv_layer].uv.length < 0.01:  # UV≈(0,0) 残留
                    loop[uv_layer].uv = (avg_u, avg_v)
                    zero_fixed += 1
    print(f"  UV=(0,0)残留修复: {zero_fixed} loops → avg_uv")
    # v43: 从删面前捕获的眼区样本构建 XZ→UV 查找表(IDW), 把贴图画好的眼睛细节(睫毛/虹膜)恢复回碗面.
    # 贴图眼睛本质是XZ位置的函数(原始眼区面就按XZ位置画的), 碗面是同一XZ区域重建, 故可按XZ反查.
    _eye_samples = _EYE_UV_SAMPLES.get(side, [])
    _eye_grid = None
    if len(_eye_samples) >= 16:
        _sa = np.array(_eye_samples, dtype=np.float64)  # (dx, dz, u, v)
        _sx, _sz, _su, _sv = _sa[:,0], _sa[:,1], _sa[:,2], _sa[:,3]
        _lim = 0.016   # 网格覆盖±16mm(略大于碗口径15mm)
        _GRID = 40
        _xs = np.linspace(-_lim, _lim, _GRID)
        _zs = np.linspace(-_lim, _lim, _GRID)
        _gridU = np.zeros((_GRID,_GRID)); _gridV = np.zeros((_GRID,_GRID))
        for _i in range(_GRID):
            _dx = _xs[_i] - _sx
            _dx2 = _dx*_dx
            for _j in range(_GRID):
                _dz = _zs[_j] - _sz
                _w = 1.0/(_dx2 + _dz*_dz + 1e-10)   # IDW权重(距离平方倒数, 近邻主导)
                _gridU[_i,_j] = (_w*_su).sum()/_w.sum()
                _gridV[_i,_j] = (_w*_sv).sum()/_w.sum()
        def _bowl_uv_lookup(dx, dz):
            _fx = (dx + _lim)/(2*_lim)*(_GRID-1)
            _fz = (dz + _lim)/(2*_lim)*(_GRID-1)
            _ix = int(max(0, min(_GRID-2, _fx)))
            _iz = int(max(0, min(_GRID-2, _fz)))
            _tx = max(0.0, min(1.0, _fx-_ix)); _tz = max(0.0, min(1.0, _fz-_iz))
            _a=_gridU[_ix,_iz]; _b=_gridU[_ix+1,_iz]; _c=_gridU[_ix,_iz+1]; _d=_gridU[_ix+1,_iz+1]
            u = _a*(1-_tx)*(1-_tz) + _b*_tx*(1-_tz) + _c*(1-_tx)*_tz + _d*_tx*_tz
            _a=_gridV[_ix,_iz]; _b=_gridV[_ix+1,_iz]; _c=_gridV[_ix,_iz+1]; _d=_gridV[_ix+1,_iz+1]
            v = _a*(1-_tx)*(1-_tz) + _b*_tx*(1-_tz) + _c*(1-_tx)*_tz + _d*_tx*_tz
            return (u, v)
        _eye_grid = True
        print(f"  v43: bowl UV lookup grid {_GRID}x{_GRID} built from {len(_eye_samples)} eye samples")
    else:
        print(f"  v43: WARNING only {len(_eye_samples)} eye samples, fallback to avg_uv")
    # v44: UV分配用拓扑标记(per-side tag层), 不再用径向距离启发式.
    # v43b根因(定量证实): 杏仁形ring0半径随角度3.9~13.8mm变化, 固定12/15/18mm分段错位 →
    #   ①上下睑(ring0≈4-6mm)的原始眼睑皮肤被套眼睛查找表 → 睫毛渗到眼睑皮肤, 开口显宽圆+拉伸带
    #   ②眼角倒角带(12~18mm)被写常数avg_uv → 眼角"贴片"伪影
    #   ③15-21mm带1139/1139原始皮肤面全被覆盖成常数UV(诊断实测)
    # 修复: 只给标记面分配UV(倒角带=1/碗=2, 用眼睛贴图XZ查找=重建该处原始贴图映射,
    #       倒角外缘与相邻皮肤贴图自然连续); 原始皮肤UV一律不动. 查找表按顶点取样(平滑梯度).
    _tag_l2 = bm.faces.layers.int.get("v44tag_" + side)
    assigned = 0
    bowl_mapped = 0
    chamfer_mapped = 0
    if _tag_l2 is None:
        print("  v44 WARNING: tag layer lost after mode roundtrip, tagged faces will fallback avg_uv")
    for f in bm.faces:
        tg = f[_tag_l2] if _tag_l2 is not None else 0
        if tg == 0:
            continue   # 原始皮肤: UV不动(关键! 不再覆盖)
        for loop in f.loops:
            vc = loop.vert.co
            if _eye_grid is not None:
                du, dv = _bowl_uv_lookup(vc.x - center.x, vc.z - center.z)
            else:
                du, dv = (avg_u, avg_v)
            loop[uv_layer].uv = (du, dv)
            assigned += 1
        if tg == 2: bowl_mapped += 1
        else: chamfer_mapped += 1
    bmesh.update_edit_mesh(mesh)
    # v46: 最终翻转pass - 用tag层(倒角带=1/碗=2/原始皮肤=0)只处理新创建面.
    # 根因: y范围判断(center.y<fc.y)漏掉倒角带上半部分靠前的面(y<center.y).
    _flip2 = 0
    _tag_fl = bm.faces.layers.int.get("v44tag_" + side)
    for _f in bm.faces:
        _tg = _f[_tag_fl] if _tag_fl is not None else 0
        if _tg == 0:
            continue   # 原始皮肤面不动
        if _f.normal.y > 0.05:
            bmesh.ops.reverse_faces(bm, faces=[_f])
            _flip2 += 1
    if _flip2:
        bm.normal_update()
        bmesh.update_edit_mesh(mesh)
        print(f"  final flip: {_flip2} residual flipped faces")
    print(f"  v44拓扑UV: 碗={bowl_mapped}面 倒角带={chamfer_mapped}面 {assigned}loops(原始皮肤UV未动)")
    # 验证UV
    us = [loop[uv_layer].uv.x for f in bm.faces for loop in f.loops]
    vs = [loop[uv_layer].uv.y for f in bm.faces for loop in f.loops]
    print(f"  UV分配: {assigned} loops, 碗面贴图映射={bowl_mapped}面, avg=({avg_u:.4f},{avg_v:.4f}), u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_cup {side}: ring0={M} bowl_faces={len(new_faces)} depth={max_depth*1000:.1f}mm")
    return ring0


def finish_socket_boolean(obj, center, side):
    """v63(2026-09-14): boolean 切割模式的收尾.
    make_eye_socket 已用棱柱 EXACT DIFFERENCE 切出眼窝 pit(竖直壁+平底), 开口边界=手描轮廓折线
    (spike实测: 到轮廓偏差 中位0.0000mm/max0.047mm, 222顶点; 旧洪泛边界 max~0.9mm), 并已打 tag=2.
    本函数只做收尾: 眼区 UV 重建映射(复用 v43 IDW 查找表) + 法线校正. 不找环/不松弛/不建碗.
    """
    mesh = obj.data
    center = Vector(center)
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
    _tag_l = bm.faces.layers.int.get("v44tag_" + side)
    if _tag_l is None:
        print(f"finish_socket_boolean {side}: WARNING tag层丢失, 跳过")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    pit = [f for f in bm.faces if f[_tag_l] == 2]
    # ---- 皮肤UV基准(下眼睑皮肤区, 同 v42b 判据) ----
    tex_img = None
    for _m in obj.data.materials:
        if _m and _m.use_nodes:
            for _n in _m.node_tree.nodes:
                if _n.type == 'TEX_IMAGE' and _n.image:
                    tex_img = _n.image
    _tex_px = tex_img.pixels[:] if tex_img else None
    _TW, _TH = tex_img.size if tex_img else (0, 0)
    def _uv_bright(u, v):
        if not _tex_px:
            return 1.0
        _x = min(max(int(u*_TW), 0), _TW-1); _y = min(max(int(v*_TH), 0), _TH-1)
        _i = (_y*_TW + _x)*4
        return (_tex_px[_i] + _tex_px[_i+1] + _tex_px[_i+2]) / 3
    skin_uvs = []
    for v in bm.verts:
        dx = v.co.x - center.x; dz = v.co.z - center.z
        dxz = math.sqrt(dx*dx + dz*dz)
        if dz < -0.008 and 0.6 * EYE_AREA_R < dxz < EYE_AREA_R and v.co.y < center.y:
            for loop in v.link_loops:
                uv = loop[uv_layer].uv
                if 0.01 < uv.x < 0.99 and 0.01 < uv.y < 0.99 and _uv_bright(uv.x, uv.y) > 0.40:
                    skin_uvs.append(uv.copy())
                break
    if skin_uvs:
        _us = sorted([u.x for u in skin_uvs]); _vs = sorted([u.y for u in skin_uvs])
        avg_u, avg_v = _us[len(_us)//2], _vs[len(_vs)//2]
    else:
        avg_u, avg_v = 0.5, 0.5
    # ---- v43 IDW 查找表: XZ→UV(把贴图里画好的眼睛细节映射回眼窝面) ----
    _eye_samples = _EYE_UV_SAMPLES.get(side, [])
    _eye_grid = None
    if len(_eye_samples) >= 16:
        _sa = np.array(_eye_samples, dtype=np.float64)
        _sx, _sz, _su, _sv = _sa[:, 0], _sa[:, 1], _sa[:, 2], _sa[:, 3]
        _lim = 0.016
        _GRID = 40
        _xs = np.linspace(-_lim, _lim, _GRID)
        _zs = np.linspace(-_lim, _lim, _GRID)
        _gridU = np.zeros((_GRID, _GRID)); _gridV = np.zeros((_GRID, _GRID))
        for _i in range(_GRID):
            _dx = _xs[_i] - _sx; _dx2 = _dx*_dx
            for _j in range(_GRID):
                _dz = _zs[_j] - _sz
                _w = 1.0/(_dx2 + _dz*_dz + 1e-10)
                _gridU[_i, _j] = (_w*_su).sum()/_w.sum()
                _gridV[_i, _j] = (_w*_sv).sum()/_w.sum()
        def _lookup(dx, dz):
            _fx = (dx + _lim)/(2*_lim)*(_GRID-1); _fz = (dz + _lim)/(2*_lim)*(_GRID-1)
            _ix = int(max(0, min(_GRID-2, _fx))); _iz = int(max(0, min(_GRID-2, _fz)))
            _tx = max(0.0, min(1.0, _fx-_ix)); _tz = max(0.0, min(1.0, _fz-_iz))
            _a = _gridU[_ix, _iz]; _b = _gridU[_ix+1, _iz]; _c = _gridU[_ix, _iz+1]; _d = _gridU[_ix+1, _iz+1]
            u = _a*(1-_tx)*(1-_tz) + _b*_tx*(1-_tz) + _c*(1-_tx)*_tz + _d*_tx*_tz
            _a = _gridV[_ix, _iz]; _b = _gridV[_ix+1, _iz]; _c = _gridV[_ix, _iz+1]; _d = _gridV[_ix+1, _iz+1]
            v = _a*(1-_tx)*(1-_tz) + _b*_tx*(1-_tz) + _c*(1-_tx)*_tz + _d*_tx*_tz
            return (u, v)
        _eye_grid = True
    # ---- UV 分配: 只动 pit 面, 原始皮肤面 UV 一律不动 ----
    assigned = 0
    for f in pit:
        for loop in f.loops:
            vc = loop.vert.co
            if _eye_grid is not None:
                du, dv = _lookup(vc.x - center.x, vc.z - center.z)
            else:
                du, dv = (avg_u, avg_v)
            loop[uv_layer].uv = (du, dv)
            assigned += 1
    bmesh.update_edit_mesh(mesh)
    # ---- 法线: pit 面必须朝 -Y(可见侧) ----
    _flip = 0
    for f in pit:
        if f.normal.y > 0.05:
            bmesh.ops.reverse_faces(bm, faces=[f])
            _flip += 1
    if _flip:
        bm.normal_update()
    bmesh.update_edit_mesh(mesh)
    _ny = [f.normal.y for f in pit] or [0.0]
    print(f"finish_socket_boolean {side}: pit面 {len(pit)}(tag=2) UV重映射 {assigned} loops "
          f"(查找表{'有' if _eye_grid else '无'}) 翻转 {_flip} normal.y[{min(_ny):.2f},{max(_ny):.2f}]")
    bpy.ops.object.mode_set(mode='OBJECT')
