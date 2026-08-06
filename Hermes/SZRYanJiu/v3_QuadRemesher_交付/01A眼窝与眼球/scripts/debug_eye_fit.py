"""debug: 定量诊断眼球装配问题
1. 原始高模眼区表面形貌: 找眼球鼓包顶点(apex)位置
2. 眼窝blend开口边界环: 中心/范围/深度
3. 已摆入眼球: 球心/前极/后极 vs 碗底
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye_socket_config import IN_BLEND as REPAIR_BLEND

d = json.load(open(DDFA_JSON, encoding="utf-8"))

# ---- Part 1: 原始高模眼区表面形貌 ----
print("### PART 1: original highpoly surface around eyes ###")
bpy.ops.wm.open_mainfile(filepath=REPAIR_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv*3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3)

for side, key in [("L", "L"), ("R", "R")]:
    c = np.array(d[key]["center_3d"], dtype=np.float32)
    dx = V[:, 0] - c[0]; dz = V[:, 2] - c[2]
    r2 = dx*dx + dz*dz
    near = r2 < 0.020**2   # 20mm半径内
    sub = V[near]
    i_apex = np.argmin(sub[:, 1])
    apex = sub[i_apex]
    print(f"{side}: 3DDFA_center={np.round(c,4)}")
    print(f"  apex(most-front)={np.round(apex,4)} dist_xz_from_center={np.hypot(apex[0]-c[0],apex[2]-c[2])*1000:.1f}mm")
    ys = sub[:, 1]
    print(f"  y-percentiles p0={ys.min():.4f} p5={np.percentile(ys,5):.4f} p50={np.percentile(ys,50):.4f}")
    # 鼓包顶点: y < 3DDFA中心y 的顶点
    n_front = int((ys < c[1]).sum())
    print(f"  verts in front of 3DDFA center: {n_front}/{len(sub)}")

# ---- Part 2: 眼窝blend开口边界环 ----
print("### PART 2: socket boundary ring in 01_1 blend ###")
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
mesh = obj.data
nv = len(mesh.vertices)
V = np.empty(nv*3, dtype=np.float32)
mesh.vertices.foreach_get("co", V)
V = V.reshape(nv, 3)

# 开放边检测需要bmesh
import bmesh
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
bm.edges.ensure_lookup_table()
open_edges = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in bm.edges if len(e.link_faces) == 1]
bpy.ops.object.mode_set(mode='OBJECT')
print(f"total open edges in blend: {len(open_edges)}")

for side, key in [("L", "L"), ("R", "R")]:
    c = np.array(d[key]["center_3d"], dtype=np.float32)
    ring_pts = []
    for a, b in open_edges:
        m = (np.array(a) + np.array(b)) / 2
        if np.hypot(m[0]-c[0], m[2]-c[2]) < 0.030:
            ring_pts.append(np.array(a)); ring_pts.append(np.array(b))
    if not ring_pts:
        print(f"{side}: NO ring found near {c}")
        continue
    ring_pts = np.array(ring_pts)
    # 去重
    ring_pts = np.unique(np.round(ring_pts, 5), axis=0)
    print(f"{side}: ring verts={len(ring_pts)}")
    print(f"  x: [{ring_pts[:,0].min():.4f}, {ring_pts[:,0].max():.4f}] center={ring_pts[:,0].mean():.4f} width={(ring_pts[:,0].max()-ring_pts[:,0].min())*1000:.1f}mm")
    print(f"  y: [{ring_pts[:,1].min():.4f}, {ring_pts[:,1].max():.4f}] mean={ring_pts[:,1].mean():.4f}")
    print(f"  z: [{ring_pts[:,2].min():.4f}, {ring_pts[:,2].max():.4f}] center={ring_pts[:,2].mean():.4f} height={(ring_pts[:,2].max()-ring_pts[:,2].min())*1000:.1f}mm")
    # 碗底(最深处顶点在ring范围xz内)
    cx, cz = ring_pts[:,0].mean(), ring_pts[:,2].mean()
    dx = V[:,0]-cx; dz = V[:,2]-cz
    inside = (dx*dx + dz*dz) < 0.015**2
    sub = V[inside]
    print(f"  cup deepest y inside ring: {sub[:,1].max():.4f}")

# ---- Part 3: 已摆入的眼球 ----
print("### PART 3: placed eyeballs in 01_2 blend ###")
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
for o in bpy.data.objects:
    if o.type == 'MESH' and 'Eye' in o.name:
        c = np.array(o.location[:])
        r = 0.0145
        print(f"{o.name}: center={np.round(c,4)} front_pole_y={c[1]-r:.4f} back_pole_y={c[1]+r:.4f}")
