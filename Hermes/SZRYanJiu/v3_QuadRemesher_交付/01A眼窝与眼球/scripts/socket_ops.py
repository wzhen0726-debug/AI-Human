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

def load_eyelid_contour(side):
    """读3DDFA眼睑轮廓(杏仁形), 返回(x,z)多边形顶点列表(顺时针/逆时针均可).
    用6点: 外眦-上睑x2-内眦-下睑x2 围成真实眼形."""
    import json
    d = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
    rim = [r for r in d[side]["rim_3d"] if r is not None]
    # 投影到x-z平面(开孔在面朝前的平面上)
    poly = [(r[0], r[2]) for r in rim]
    return poly

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
    """对单侧眼睛做开孔+压凹. center为局部坐标"""
    mesh = obj.data
    center = Vector(center)
    
    # ---- 1. 选中开口内面片并删除 ----
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    
    # 用numpy快速找开口内顶点
    nv = len(mesh.vertices)
    V = np.empty(nv*3, dtype=np.float32)
    mesh.vertices.foreach_get("co", V)
    V = V.reshape(nv,3)
    
    cx, cy, cz = center.x, center.y, center.z
    rx, rz = HOLE_RX, HOLE_RZ
    
    # 椭圆: ((x-cx)/rx)^2 + ((z-cz)/rz)^2 <= 1
    dx = (V[:,0] - cx) / rx
    dz = (V[:,2] - cz) / rz
    in_ellipse = (dx*dx + dz*dz <= 1.0) & (V[:,1] < cy + 0.005)
    
    # 2026-08-07: 用3DDFA真实眼睑轮廓(杏仁多边形)开孔, 不用对称椭圆.
    # 真实眼形26.8x9.7mm宽高比2.75两头尖; 对称椭圆rz=9太圆(宽高比1.44).
    poly = load_eyelid_contour(side) if USE_EYELID_CONTOUR else None
    y_cut = cy + 0.005  # 角膜点后5mm以内的面都删(覆盖眼睑前凸)
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    to_delete = []
    for f in bm.faces:
        fc = f.calc_center_median()
        if poly is not None:
            inside = point_in_polygon(fc.x, fc.z, poly)
        else:
            dx = (fc.x - cx) / rx
            dz = (fc.z - cz) / rz
            inside = (dx*dx + dz*dz <= 1.0)
        if inside and fc.y < y_cut:
            to_delete.append(f)
    bmesh.ops.delete(bm, geom=to_delete, context='FACES')
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: deleted {len(to_delete)} faces by center, n_verts_in={in_ellipse.sum()}")
    
    # ---- 2. 压凹 ----
    # ---- 2. 压凹 (2026-08-07: 默认关闭, 是星爆源头) ----
    # ---- 2. 压凹已移除 (2026-08-07: 压凹是星爆源头, 杏仁尖角顶点压得最深->锯齿/碎面) ----
    # 凹陷由make_eye_cup的碗负责, 删面后的洞边缘保持脸面原平滑曲面, 不做压凹.
    print(f"make_eye_socket {side}: push-in removed (凹陷由碗负责)")
    
    # ---- 3. 局部清理（禁止全局Shift+N） ----
    # 历史教训: bpy.ops.mesh.normals_make_consistent(inside=False) 在删面后的非封闭网格上
    # 是非确定性传播(等效Shift+N), 会翻过洞边缘把下半身大片法线搞反(2026-08-06实测).
    # 01_highpoly_repair.blend 法线本来就正确, 绝不能全局重算.
    # 删面+压凹只动顶点位置, 不改面绕序(winding), 法线方向保持原样即可.
    # 只做局部焊接: 合并洞口边缘的重复顶点(压凹可能让边界顶点重叠)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: cleanup done (local weld only, no global recalc)")


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
    """眼窝碗底封口: 边界环(拓扑闭环)垂直内移 + ngon平底封口.
    
    用户明确: 眼窝内部是个坑就行(有眼球挡着). 直筒平底坑, 零穿插.
    2026-08-07: 历经多环收缩星爆/独立网格脱开等坑, 最终用最简可靠方案.
    """
    import math
    mesh = obj.data
    center = Vector(center)
    max_depth = CUP_DEPTH
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # ---- 1. 拓扑法找开口边界环: 从开放边出发沿闭环走一圈(精确, 不用距离阈值) ----
    # 2026-08-07: 距离阈值法误识别(70 vs 真实38). 改用拓扑: 开放边首尾相连成闭环=真边界.
    from collections import defaultdict
    def is_open(e): return len(e.link_faces) == 1
    open_edges = [e for e in bm.edges if is_open(e)]
    v2e = defaultdict(list)
    for e in open_edges:
        v2e[e.verts[0].index].append(e)
        v2e[e.verts[1].index].append(e)
    def near(v): return (v.co.x-center.x)**2 + (v.co.z-center.z)**2 < 0.020**2
    starts = [e for e in open_edges if near(e.verts[0])]
    ring0 = []
    if starts:
        e0 = starts[0]; first_v = e0.verts[0]; v = first_v; prev_idx = -1
        for _ in range(2000):
            ring0.append(v)
            nxt_v = None
            for x in v2e[v.index]:
                if not is_open(x): continue
                ov = x.verts[1] if x.verts[0].index == v.index else x.verts[0]
                if ov.index == first_v.index and len(ring0) > 2:
                    nxt_v = ov; break
                if ov.index != prev_idx:
                    nxt_v = ov; break
            if nxt_v is None or nxt_v.index == first_v.index: break
            prev_idx = v.index; v = nxt_v
    boundary_verts = ring0
    
    if len(boundary_verts) < 3:
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"make_eye_cup {side}: WARNING only {len(boundary_verts)} boundary verts, skip")
        return
    
    # ring0已是拓扑有序闭环(行走顺序), 直接用
    M = len(ring0)
    rim_y = sum(v.co.y for v in ring0) / M   # 用环的实际平均深度作基准
    
    # ---- 2/3. 均匀角度球面碗: 内部环用均匀角度分布(消星爆), 第0圈=ring0 ----
    # 2026-08-07定量确诊: ring0顶点间距0.7~2.9mm不均(std0.49), 收缩时弧线quad被拉成狭长三角→星爆.
    # 实测: 均匀角度48点+球面剖面 → 碗心平滑无星爆(vision确认). 
    # 方案: 第0圈=ring0(保缝合), 内部环用均匀角度插值ring0位置(保对应关系防穿插).
    import math
    N = CUP_RINGS  # 8环
    # 把ring0按角度重排并均匀重采样到M个点(保顶点数=保缝合对应), 内部环用它做基准
    def ang_of(v): return math.atan2(v.co.z - center.z, v.co.x - center.x)
    # 均匀角度目标: 每个顶点的"理想角度"=等分圆周, 在ring0上插值出该角度的位置
    ring_sorted = sorted(ring0, key=ang_of)
    # 计算每个顶点的累计角度
    angs = [ang_of(v) for v in ring_sorted]
    # 强制单调(处理2π跳变)
    for i in range(1, len(angs)):
        while angs[i] < angs[i-1]: angs[i] += 2*math.pi
    span = angs[-1] - angs[0]
    def pos_at_angle(theta):
        # 在ring_sorted上按角度线性插值位置
        th = angs[0] + theta
        for i in range(len(ring_sorted)-1):
            if angs[i] <= th <= angs[i+1]:
                t = (th-angs[i])/(angs[i+1]-angs[i]) if angs[i+1]>angs[i] else 0
                a, b = ring_sorted[i].co, ring_sorted[i+1].co
                return a + (b-a)*t
        return ring_sorted[-1].co
    vgrid = [ring0]  # 第0圈=真实边界环(缝合)
    for j in range(1, N):
        t = j / N   # 0..1, 0=口沿 1=碗底
        row = []
        for i in range(M):
            # 该顶点的均匀角度
            theta = span * i / M
            # 在ring0上取该角度的位置(均匀化), 再向质心收缩
            base = pos_at_angle(theta)
            ox, oz = base.x - center.x, base.z - center.z
            # 2026-08-07: 16环+半球面剖面. 收缩=cos²(t·π/2)口沿更缓, 加深=sin(t·π/2)连续.
            # 口沿坡度放缓, 消除开口边缘的陡坎硬边(用户报衔接硬边).
            ang = t * math.pi / 2
            scale = math.cos(ang) ** 1.5      # 口沿收缩更缓(指数>1 -> 前期变化慢)
            depth_frac = math.sin(ang)         # 深度连续
            x = center.x + ox * scale
            z = center.z + oz * scale
            y = base.y + (rim_y + max_depth - base.y) * depth_frac
            row.append(bm.verts.new((x, y, z)))
        vgrid.append(row)
    # 碗底用最后一环ngon封口, 不需要极点顶点
    # 创建面: 相邻环quad
    new_faces = []
    for j in range(N - 1):
        for i in range(M):
            i2 = (i+1) % M
            a=vgrid[j][i]; b=vgrid[j][i2]; c=vgrid[j+1][i2]; d=vgrid[j+1][i]
            try: new_faces.append(bm.faces.new((a,d,c,b)))
            except ValueError: pass
    # 碗底: 最后一环ngon封平(不用单极点防星爆)
    last = vgrid[N-1]
    try: new_faces.append(bm.faces.new(tuple(last)))
    except ValueError: pass
    bmesh.update_edit_mesh(mesh)
    
    # ---- 4. 局部法线校正: 碗内面必须朝-Y(朝眼球/朝外). 2026-08-07用户报面朝向反 ----
    # ring0排序绕向不定(atan2顺/逆), 导致生成面法线可能朝内(+Y). 逐个检查翻转.
    # 只动刚生成的碗面(new_faces), 不全局重算(历史教训: 全局Shift+N会翻过洞边缘).
    bm.faces.ensure_lookup_table()
    flipped = 0
    for f in new_faces:
        if f.is_valid and f.normal.y > 0:  # 法线朝+Y=朝头内=反了
            f.normal_flip()
            flipped += 1
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_cup {side}: ring0={M} faces={len(new_faces)} depth={max_depth*1000:.1f}mm normal_flipped={flipped}")
    return ring0
