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
    rim_y = sum(v.co.y for v in ring0) / M
    print(f"make_eye_cup {side}: boundary ring M={M} (of {len(rings)} rings)")
    
    # ---- 2. 同序收缩3圈 + 极点扇封底 ----
    # 内圈=ring0[i]径向收缩(同一顶点同一顺序) -> quad必共享边界边, 零悬空边.
    vgrid = [list(ring0)]
    NR = 3
    for j in range(1, NR+1):
        t = j / (NR+1)
        scale = 1.0 - t*0.60
        row = []
        for i in range(M):
            base = ring0[i].co
            x = center.x + (base.x-center.x)*scale
            z = center.z + (base.z-center.z)*scale
            y = base.y + (rim_y + max_depth - base.y)*(t*0.7)
            row.append(bm.verts.new((x,y,z)))
        vgrid.append(row)
    pole = bm.verts.new((center.x, rim_y+max_depth, center.z))
    
    new_faces = []
    # 相邻环quad
    for j in range(len(vgrid)-1):
        for i in range(M):
            i2=(i+1)%M
            a=vgrid[j][i]; b=vgrid[j][i2]; c=vgrid[j+1][i2]; d=vgrid[j+1][i]
            try: new_faces.append(bm.faces.new((a,d,c,b)))
            except ValueError: pass
    # 极点扇封底(不用ngon, 防翘曲条纹)
    last = vgrid[-1]
    for i in range(M):
        try: new_faces.append(bm.faces.new((last[i], last[(i+1)%M], pole)))
        except ValueError: pass
    
    # smooth shading(与皮肤一致, 消棱面)
    for f in new_faces:
        f.smooth = True
    bmesh.update_edit_mesh(mesh)
    
    # ---- 3. 法线校正: 碗面朝-Y(朝眼球) ----
    bm.faces.ensure_lookup_table()
    flipped = 0
    for f in new_faces:
        if f.is_valid and f.normal.y > 0:
            f.normal_flip()
            flipped += 1
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_cup {side}: ring0={M} faces={len(new_faces)} depth={max_depth*1000:.1f}mm normal_flipped={flipped}")
    return ring0
