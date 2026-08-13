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

def load_eyelid_contour(side, n_points=24, margin_x_mm=2.0, margin_z_mm=1.0, outer_extra_mm=4.0, inner_extra_mm=1.5):
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
    
    # ---- 1.5 松弛ring0去锯齿(3次Laplace) ----
    # 2026-08-07 v12: 锯齿口沿(vision反复报的尖刺)+碗底非流形边(0.3mm sliver,4面共边)
    # 同一根因=边界环局部zigzag. 收缩后zigzag的quad重叠->非流形. 松弛ring0:
    # 顶点与皮肤共享, 移动它同时平滑了洞口边缘(正是我们要的).
    for _ in range(3):
        new_pos = {}
        for i, v in enumerate(ring0):
            a = ring0[(i-1)%M].co; b = ring0[(i+1)%M].co
            new_pos[v.index] = v.co*0.5 + (a+b)*0.25
        for v in ring0:
            v.co = new_pos[v.index]
    rim_y = sum(v.co.y for v in ring0) / M
    print(f"make_eye_cup {side}: boundary ring M={M} (of {len(rings)} rings), ring relaxed x3")
    
    # 保存ring0顶点索引(后续mode切换可能使引用失效)
    ring0_indices = [v.index for v in ring0]
    
    # ---- 2. 球面碗剖面 + 共享极点三角扇封底(构造上保证流形) ----
    # 2026-08-07 v11根因总结: ngon封口(三角化碎片)/pointmerge(碗底重复面)都留非流形边.
    # 唯一构造上零碎片的方式=单个共享极点顶点+三角扇(经典UV球极点拓扑, 每条边恰好2面).
    # 8圈球面收缩让极点扇只在碗底最小一圈, smooth shading消棱. 碗内有眼球挡, 不讲究.
    # 2026-08-13 v26: 给碗面新顶点分配UV(径向对应ring0), 修复破面(新顶点UV=(0,0)采样贴图角落)
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
    # ring0顶点的UV (取每个顶点第一个loop)
    ring0_uv = {}
    for v in ring0:
        for loop in v.link_loops:
            ring0_uv[v.index] = loop[uv_layer].uv.copy()
            break
    avg_uv = sum((uv for uv in ring0_uv.values()), Vector((0.0, 0.0))) / max(len(ring0_uv), 1)
    vgrid = [list(ring0)]
    NR = 24  # v27: 8→24环, 高模需要更多面数做圆润过渡(smoothstep剖面)
    for j in range(1, NR):     # 环1..NR-1(不到底)
        t = j / NR
        # v27: smoothstep剖面(t²(3-2t)), 口沿坡度=0(与皮肤切向连续), 碗底平缓收拢
        s = t * t * (3 - 2 * t)   # smoothstep
        scale = 1.0 - s           # 半径收缩
        depth_frac = s            # 深度
        row = []
        for i in range(M):
            base = ring0[i].co
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
    
    # v26: 给碗面loop分配UV. 新顶点径向对应ring0[i]的UV, pole用平均UV.
    # 碗面内部(最终被眼球挡)颜色跟随眼周肤色, 不突兀.
    v2uv = {}
    for i in range(M):
        v2uv[vgrid[0][i].index] = ring0_uv[ring0[i].index]
        for j in range(1, NR):
            v2uv[vgrid[j][i].index] = ring0_uv[ring0[i].index]
    v2uv[pole.index] = avg_uv
    for f in new_faces:
        for loop in f.loops:
            uvidx = loop.vert.index
            if uvidx in v2uv:
                loop[uv_layer].uv = v2uv[uvidx]
    
    # smooth shading(与皮肤一致, 消棱面)
    for f in new_faces:
        f.smooth = True
    bmesh.update_edit_mesh(mesh)
    
    # 2026-08-07 v14: 溶解封碗后才变内部的反向sliver(口沿皮肤碎片, 删面时在边界上没敢溶).
    # 封碗后它们变内部, 0.1um²且法线朝+Y(反), 是锯齿尖刺根因. 只溶严格内部面.
    # 2026-08-13 v23: 加z上限<1.678, 同make_eye_socket, 防触及眉毛区.
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    flipped_slivers = [f for f in bm.faces
                       if f.calc_area() < 0.5e-6 and f.normal.y > 0.3
                       and (f.calc_center_median()-center).xz.length < 0.015
                       and f.calc_center_median().z < 1.678
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
    # 专家方案: 废弃normal.y硬编码判断+reverse_faces手动绕序.
    # 收集碗面+缓冲带面+参考皮肤面, 让Blender底层C++顺着正确的皮肤拓扑统一法线朝外.
    # 先保存ring0顶点索引(mode切换后引用失效) — 已在缓冲环段保存, 此处复用
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    # 重建ring0引用
    ring0_rebuilt = [bm.verts[i] for i in ring0_indices]
    # 碗面 = 碗区内的面
    bowl_zone = [f for f in bm.faces
                 if (f.calc_center_median() - center).xz.length < 0.014]
    # 参考皮肤面 = ring0外侧相邻的皮肤三角面(法线绝对正确)
    ref_faces = []
    for v in ring0_rebuilt:
        for f in v.link_faces:
            if len(f.verts) == 3 and f not in ref_faces:
                ref_faces.append(f)
    # 去重: bowl_zone可能已包含部分ref_faces(碗区边缘)
    ref_unique = [f for f in ref_faces if f not in bowl_zone]
    if bowl_zone and ref_unique:
        try:
            bmesh.ops.recalc_face_normals(bm, faces=bowl_zone + ref_unique)
            bmesh.update_edit_mesh(mesh)
            print(f"  recalc_face_normals: {len(bowl_zone)} bowl + {len(ref_unique)} ref faces")
        except Exception as e:
            print(f"  recalc_face_normals failed: {e}")
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_cup {side}: ring0={M} bowl_faces={len(new_faces)} depth={max_depth*1000:.1f}mm")
    return ring0
