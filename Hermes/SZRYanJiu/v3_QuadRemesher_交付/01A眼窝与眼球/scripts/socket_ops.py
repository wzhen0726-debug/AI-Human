"""01_1眼窝制作 - 开孔与压凹

步骤:
1. 按虹膜中心+椭圆尺寸选中开口内面片, 删除成洞
2. 开口周围顶点沿"全局前向(-Y)"压凹, 平滑衰减, 最深10mm
3. 清理边界环, 重算法线
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from eye_socket_config import *

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

def make_eye_socket(obj, center, side):
    """开孔: 删面心在眼睑轮廓(杏仁多边形)内的所有面, 不分深度全删净.
    2026-08-07重写: 旧y_cut条件让深部鼓包面残留成孤岛(45条开放边/5断环)→锯齿破面."""
    mesh = obj.data
    center = Vector(center)
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    
    poly = load_eyelid_contour(side) if USE_EYELID_CONTOUR else None
    cx, cy, cz = center.x, center.y, center.z
    rx, rz = HOLE_RX, HOLE_RZ
    
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    # 2026-08-07 v4: 洪泛填充删面(替代面心判断). 面心判断让删区不连通, 留5个孤立环(锯齿破面).
    # 从眼中心最近面生长, 只收录面心在轮廓内的邻面 -> 删区必连通成单环.
    # y限制: cy+20mm(鼓包最深处~-0.10也要删净; 轮廓只覆盖眼区, 不会误删后脑壳)
    y_cut = cy + 0.020
    # 面邻接表
    f2f = {}
    for f in bm.faces:
        f2f[f.index] = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            a, b = e.link_faces[0].index, e.link_faces[1].index
            f2f[a].append(b); f2f[b].append(a)
    # 找离眼中心最近的面作种子(必须用3D距离: xz最近会选到后脑勺同x/z的面y=+0.09)
    seed = min(bm.faces, key=lambda f: (f.calc_center_median()-center).length)
    def inside_poly(fc):
        if fc.y >= y_cut: return False
        if poly is not None:
            return point_in_polygon(fc.x, fc.z, poly)
        return ((fc.x-cx)/rx)**2 + ((fc.z-cz)/rz)**2 <= 1.0
    # BFS洪泛
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
    bmesh.ops.delete(bm, geom=del_faces, context='FACES')
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: flood-fill deleted {len(del_faces)} faces (single connected patch)")
    print(f"make_eye_socket {side}: push-in removed (凹陷由碗负责)")
    
    # 局部焊接重复顶点(不动法线, 历史教训: 全局Shift+N会翻过洞边缘)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: cleanup done (local weld only, no global recalc)")
    
    # 2026-08-07 v13: 溶解口沿碎片面(<0.5mm²的sliver, 原有皮肤碎片, 法线乱->锯齿尖刺根因).
    # 只溶解严格内部面(所有边恰2面), 绝不碰边界环上的面(防开洞). ad-hoc验证抓到此缺陷.
    # 2026-08-13 v23: 加z上限<1.678(与轮廓z上沿一致), 防sliver溶解触及眉毛z>1.68→UV错乱.
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    slivers = [f for f in bm.faces
               if f.calc_area() < 0.5e-6
               and (f.calc_center_median()-center).xz.length < 0.015
               and f.calc_center_median().z < 1.678
               and all(len(e.link_faces)==2 for e in f.edges)]
    if slivers:
        bmesh.ops.dissolve_faces(bm, faces=slivers)
        bmesh.update_edit_mesh(mesh)
        # 2026-08-13 v24: 消除溶解产生的ngon(多边面→三角化, 防止法线异常/破面/布线乱)
        bm.faces.ensure_lookup_table()
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
            bmesh.update_edit_mesh(mesh)
            print(f"  triangulated {len(ngons)} ngons after dissolve")
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
    max_depth = CUP_DEPTH
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
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
    
    # ---- 1.5 松弛ring0去锯齿(v42: 3次轻度Laplace, 平衡形状保持与平滑) ----
    # v39: 12次太强(扭曲rim形状, avg偏差6.4mm), v42: 0次太弱(星爆拓扑)
    # 3次轻度松弛: 消除锯齿但保持3DDFA轮廓形状
    for _ in range(12):
        new_pos = {}
        for i, v in enumerate(ring0):
            a = ring0[(i-1)%M].co; b = ring0[(i+1)%M].co
            # v42: 固定权重0.3(轻度松弛), 避免扭曲
            w = 0.3
            new_pos[v.index] = v.co*(1-w) + (a+b)*0.5*w
        for v in ring0:
            v.co = new_pos[v.index]
    
    # v42: 松弛后径向投影回3DDFA轮廓(约束到正确位置, 消除偏离)
    # 方法: 轮廓折线密集采样建立 角度θ→半径r 插值表, 每个ring0顶点保持自身角度,
    #       半径设为r(θ). 避免最近点投影的聚簇bug(曾致jump max 6.8mm).
    import json as _json
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as _f:
        _dd = _json.load(_f)
    _pts = [(r[0]-center.x, r[2]-center.z) for r in _dd[side]["rim_3d"] if r is not None]
    # 折线密集采样(每段细分16点), 建立(θ,r)表
    _samples = []
    _n = len(_pts)
    for _i in range(_n):
        _p1 = _pts[_i]; _p2 = _pts[(_i+1)%_n]
        for _t in range(16):
            _f = _t/16
            _sx = _p1[0]+(_p2[0]-_p1[0])*_f; _sz = _p1[1]+(_p2[1]-_p1[1])*_f
            _samples.append((math.atan2(_sz, _sx), math.sqrt(_sx*_sx+_sz*_sz)))
    _samples.sort()
    _thetas = [s[0] for s in _samples]; _radii_tab = [s[1] for s in _samples]
    def _radius_at(theta):
        # 周期插值
        import bisect
        i = bisect.bisect_left(_thetas, theta)
        if i == 0 or i == len(_thetas):
            # 环绕: theta < 最小 或 >= 最大, 用首尾环绕
            t1, r1 = _thetas[-1], _radii_tab[-1]
            t2, r2 = _thetas[0], _radii_tab[0]
            if t1 > t2:  # 环绕 -π/π
                span = (t2 + 2*math.pi) - t1
                d = (theta - t1) if theta >= t1 else (theta + 2*math.pi - t1)
            else:
                span = t2 - t1; d = theta - t1
        else:
            t1, r1 = _thetas[i-1], _radii_tab[i-1]
            t2, r2 = _thetas[i], _radii_tab[i]
            span = t2 - t1; d = theta - t1
        if span <= 0: return r1
        return r1 + (r2-r1) * d / span
    
    projected = 0
    for v in ring0:
        dx = v.co.x - center.x; dz = v.co.z - center.z
        r_now = math.sqrt(dx*dx + dz*dz)
        if r_now < 1e-9: continue
        theta = math.atan2(dz, dx)
        r_target = _radius_at(theta)
        if abs(r_target - r_now) > 0.0005:  # >0.5mm才移动
            v.co.x = center.x + r_target * math.cos(theta)
            v.co.z = center.z + r_target * math.sin(theta)
            projected += 1
    print(f"  径向投影回3DDFA轮廓: {projected}/{M}顶点")
    rim_y = sum(v.co.y for v in ring0) / M
    # v39: 验证松弛效果
    _radii = [(v.co - center).xz.length for v in ring0]
    _jumps = [abs(_radii[(i+1)%M] - _radii[i]) for i in range(M)]
    print(f"make_eye_cup {side}: boundary ring M={M} (of {len(rings)} rings), ring relaxed x12, "
          f"jump avg={sum(_jumps)/len(_jumps)*1000:.2f}mm max={max(_jumps)*1000:.2f}mm")
    # v41: 打印rim半径分布(诊断交缝精度)
    _rmm = [r*1000 for r in _radii]
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
    
    # ---- 1.6 倒角过渡带 v37: 圆弧fillet(1/4圆弧精确几何, 宽度实测3mm) ----
    # v35根因: 线性插值+6轮Laplace把3mm倒角吃成实测1.1mm(用户: 接缝没变化).
    # v37: 改用几何上精确的1/4圆弧: 径向=W(1-cosθ), 深度=D·sinθ, θ∈[0,π/2].
    # 保留v35法线处理(recalc+几何兜底), 只改倒角几何和UV分配.
    import math as _math
    F = CHAMFER_FILLET_RINGS   # 中间环数(不含ring0和ring1_final)
    W = CHAMFER_WIDTH          # 倒角径向宽度(米)
    D = CHAMFER_DEPTH          # 倒角下沉深度(米)
    rad_dirs = []
    for v in ring0:
        rad = Vector((center.x - v.co.x, 0, center.z - v.co.z))
        rad_dirs.append(rad / rad.length if rad.length > 1e-9 else Vector((0,0,0)))
    fillet_rings = [list(ring0)]  # 第0环=ring0(皮肤边界, 不平滑)
    for k in range(1, F + 2):     # k=1..F中间环, k=F+1是ring1_final
        theta = (k / (F + 1)) * (_math.pi / 2.0)   # 0..π/2 圆弧
        radial = W * (1.0 - _math.cos(theta))      # 径向内收(0→W)
        depth = D * _math.sin(theta)               # 下沉(0→D)
        row = []
        for i in range(M):
            pos = ring0[i].co + rad_dirs[i] * radial + Vector((0, depth, 0))
            row.append(bm.verts.new(pos))
        fillet_rings.append(row)
    ring1 = fillet_rings[-1]  # 碗的起始环
    # 相邻环quad连接
    chamfer_faces = []
    chamfer_fail = 0
    for k in range(F + 1):  # fillet_rings[k] → fillet_rings[k+1]
        for i in range(M):
            i2 = (i + 1) % M
            try:
                f = bm.faces.new((fillet_rings[k][i], fillet_rings[k][i2],
                                  fillet_rings[k+1][i2], fillet_rings[k+1][i]))
                f.smooth = True
                chamfer_faces.append(f)
            except ValueError:
                chamfer_fail += 1
    bm.edges.ensure_lookup_table()
    # 实测倒角宽度自检
    _span = []
    for i in range(M):
        _r0 = (ring0[i].co - center).xz.length
        _r1 = (ring1[i].co - center).xz.length
        _span.append((_r0 - _r1) * 1000)
    print(f"  fillet band: {len(chamfer_faces)} faces ({F+1} strips x {M}, fail={chamfer_fail}), "
          f"实际宽度 min={min(_span):.2f}mm max={max(_span):.2f}mm avg={sum(_span)/len(_span):.2f}mm")
    
    # v32根因修复: 用坐标快照保存ring0多边形! 索引在后续dissolve+mode切换后会重排失效
    # (v31灾难: R侧ring0_indices失效→polygon乱序→几何兜底误翻184866面).
    ring0_coords = [tuple(v.co) for v in ring0]
    
    # ---- 2. 球面碗剖面 + 共享极点三角扇封底(构造上保证流形) ----
    # 2026-08-07 v11根因总结: ngon封口(三角化碎片)/pointmerge(碗底重复面)都留非流形边.
    # 唯一构造上零碎片的方式=单个共享极点顶点+三角扇(经典UV球极点拓扑, 每条边恰好2面).
    # 8圈球面收缩让极点扇只在碗底最小一圈, smooth shading消棱. 碗内有眼球挡, 不讲究.
    # 2026-08-13 v26: 给碗面新顶点分配UV(径向对应ring0), 修复破面(新顶点UV=(0,0)采样贴图角落)
    # v31: ring0_uv/uv_layer/avg_uv已在倒角带创建前捕获(见---- 1.55 ----)
    # v31: 碗从ring1(倒角带内环)开始, ring0-ring1之间是倒角过渡带
    vgrid = [list(ring1)]
    NR = 24  # v27: 8→24环, 高模需要更多面数做圆润过渡(smoothstep剖面)
    for j in range(1, NR):     # 环1..NR-1(不到底)
        t = j / NR
        # v27: smoothstep剖面(t²(3-2t)), 口沿坡度=0(与皮肤切向连续), 碗底平缓收拢
        s = t * t * (3 - 2 * t)   # smoothstep
        scale = 1.0 - s           # 半径收缩
        depth_frac = s            # 深度
        row = []
        for i in range(M):
            base = ring1[i].co
            x = center.x + (base.x-center.x)*scale
            z = center.z + (base.z-center.z)*scale
            y = base.y + (rim_y + max_depth - base.y)*depth_frac
            row.append(bm.verts.new((x,y,z)))
        vgrid.append(row)
    pole = bm.verts.new((center.x, rim_y+max_depth, center.z))  # 单个共享极点
    
    new_faces = []
    # 相邻环quad
    for j in range(len(vgrid)-1):
        for i in range(M):
            i2=(i+1)%M
            a=vgrid[j][i]; b=vgrid[j][i2]; c=vgrid[j+1][i2]; d=vgrid[j+1][i]
            try: new_faces.append(bm.faces.new((a,d,c,b)))
            except ValueError: pass
    # 极点三角扇(共享pole顶点, 每条边恰2面, 构造上流形)
    # v27: 反转绕序(last[i+1],last[i],pole)让法线朝外, 避免面朝向反了
    last = vgrid[-1]
    for i in range(M):
        try: new_faces.append(bm.faces.new((last[(i+1)%M], last[i], pole)))
        except ValueError: pass
    
    # v39 UV分配: 碗面全部用avg_uv(均匀皮肤色, 避免放射条纹/UV错乱).
    # 倒角带: ring0 loop继承皮肤UV(自然过渡), 内部环用avg_uv.
    # v39修复: UV分配移到最后(所有bmesh操作之后), 防止被update_edit_mesh覆盖.
    
    # smooth shading(与皮肤一致, 消棱面)
    for f in new_faces:
        f.smooth = True
    for f in chamfer_faces:
        f.smooth = True
    bmesh.update_edit_mesh(mesh)
    
    # 2026-08-07 v14: 溶解封碗后才变内部的反向sliver(口沿皮肤碎片, 删面时在边界上没敢溶).
    # 封碗后它们变内部, 0.1um²且法线朝+Y(反), 是锯齿尖刺根因. 只溶严格内部面.
    # 2026-08-13 v23: 加z上限<1.678, 同make_eye_socket, 防触及眉毛区.
    # 2026-08-13 v32根因修复: 加y上限<rim_y+1mm! 碗底极点三角扇面积极小(0.0001mm2级)
    # 且满足原判据 → 被误溶 → 碗底出现开放边+非流形边(实测L眼1开放边+2非流形边).
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    flipped_slivers = [f for f in bm.faces
                       if f.calc_area() < 0.5e-6 and f.normal.y > 0.3
                       and (f.calc_center_median()-center).xz.length < 0.015
                       and f.calc_center_median().z < 1.678
                       and f.calc_center_median().y < rim_y + 0.001
                       and all(len(e.link_faces)==2 for e in f.edges)]
    if flipped_slivers:
        bmesh.ops.dissolve_faces(bm, faces=flipped_slivers)
        bmesh.update_edit_mesh(mesh)
        # 2026-08-13 v24: 消除溶解产生的ngon
        bm.faces.ensure_lookup_table()
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
            bmesh.update_edit_mesh(mesh)
            print(f"  triangulated {len(ngons)} ngons after flipped_sliver dissolve")
    print(f"make_eye_cup {side}: dissolved {len(flipped_slivers)} flipped rim slivers")
    
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
        if center.y < fc.y < center.y + 0.02 and (fc - center).xz.length < 0.021:
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
                       and (f.calc_center_median() - center).xz.length < 0.021
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
        if dz < -0.008 and 0.018 < dxz < 0.030 and v.co.y < center.y:
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
    # 为眼窝区面分配UV: 倒角带用皮肤UV(连续), 碗面用avg_uv(均匀)
    assigned = 0
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if center.y < fc.y < center.y + 0.02 and dxz < 0.021:
            # 倒角带(xz 15-18mm): 继承皮肤UV
            if 0.015 < dxz < 0.018:
                # 找最近的皮肤顶点UV
                best_uv = min(skin_uvs, key=lambda x: (x[0] - fc).length_squared)[1] if skin_uvs else (avg_u, avg_v)
                for loop in f.loops:
                    loop[uv_layer].uv = best_uv
                    assigned += 1
            # 碗面(xz<15mm): avg_uv
            else:
                for loop in f.loops:
                    loop[uv_layer].uv = (avg_u, avg_v)
                    assigned += 1
    bmesh.update_edit_mesh(mesh)
    # 验证UV
    us = [loop[uv_layer].uv.x for f in bm.faces for loop in f.loops]
    vs = [loop[uv_layer].uv.y for f in bm.faces for loop in f.loops]
    print(f"  UV分配: {assigned} loops, avg=({avg_u:.4f},{avg_v:.4f}), u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")

    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_cup {side}: ring0={M} bowl_faces={len(new_faces)} depth={max_depth*1000:.1f}mm")
    return ring0
