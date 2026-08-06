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
    in_ellipse = (dx*dx + dz*dz <= 1.0) & (np.abs(V[:,1] - cy) < 0.020)
    
    # 用bmesh直接删除面中心在椭圆内的面
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    to_delete = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = (fc.x - cx) / rx
        dz = (fc.z - cz) / rz
        if dx*dx + dz*dz <= 1.0 and abs(fc.y - cy) < 0.020:
            to_delete.append(f)
    bmesh.ops.delete(bm, geom=to_delete, context='FACES')
    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"make_eye_socket {side}: deleted {len(to_delete)} faces by center, n_verts_in={in_ellipse.sum()}")
    
    # ---- 2. 压凹 ----
    # 用numpy批量处理顶点
    nv = len(mesh.vertices)
    V = np.empty(nv*3, dtype=np.float32)
    mesh.vertices.foreach_get("co", V)
    V = V.reshape(nv,3)
    
    # 压凹方向: 全局前向(-Y)的反向, 即+Y? 不对, 眼窝是往头内压, 即-Y方向
    # 模型面朝-Y, 头内是+Y? 实测: 虹膜中心y=-0.116, 头表面y更小, 头内y更大
    # 所以压凹方向是 +Y (往头内)
    push_dir = np.array([0, 1, 0], dtype=np.float32)  # +Y往头内
    
    # 计算每个顶点到虹膜中心的距离(在x-z平面)
    dx = V[:,0] - center.x
    dz = V[:,2] - center.z
    dist = np.sqrt(dx*dx + dz*dz)
    
    # 压凹权重: 中心1.0, 边缘0.0, 平滑衰减 (cosine falloff)
    R = SOCKET_RADIUS
    w = np.clip(1.0 - dist / R, 0, 1)
    w = 0.5 * (1 + np.cos(np.pi * (1 - w)))  # smooth cosine
    
    # 深度: 中心最深 SOCKET_DEPTH, 边缘0
    depth = w * SOCKET_DEPTH
    
    # 只压凹开口周围, 排除开口内(椭圆内的顶点不压)
    # 删面后顶点索引已变, 需重新计算 in_ellipse
    dx2 = (V[:,0] - cx) / rx
    dz2 = (V[:,2] - cz) / rz
    in_ellipse_new = (dx2*dx2 + dz2*dz2 <= 1.0) & (np.abs(V[:,1] - cy) < 0.020)
    
    # 压凹范围: 椭圆外 且 dist < R
    mask = (dist < R) & (~in_ellipse_new)
    V[mask] += push_dir * depth[mask, np.newaxis]
    
    mesh.vertices.foreach_set("co", V.ravel())
    mesh.update()
    print(f"make_eye_socket {side}: pushed {mask.sum()} verts, max_depth={SOCKET_DEPTH*1000:.1f}mm")
    
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
