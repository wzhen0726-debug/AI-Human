"""diagnose_v41_fit2: 用倒角带外环(最浅一圈)作为rim参考, 对比输入模型眼睑边缘"""
import bpy, os, sys, json, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj_out = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm_out = bmesh.new(); bm_out.from_mesh(obj_out.data)
bm_out.verts.ensure_lookup_table()

# rim = 倒角带最浅一圈(最接近皮肤表面的新面环)
# 找眼窝区最浅(y最小)的面环
for side, center in [("L", cL), ("R", cR)]:
    # 找眼窝区所有面, 按深度分桶
    depth_faces = {}
    for f in bm_out.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz >= 0.020: continue
        depth = fc.y - center.y
        if depth > 0.015: continue  # 只取最浅15mm
        bucket = int(depth * 1000 // 2) * 2  # 2mm桶
        if bucket not in depth_faces: depth_faces[bucket] = []
        depth_faces[bucket].append(f)
    # 最浅的非零桶 = rim
    sorted_buckets = sorted(depth_faces.keys())
    print(f"\n{side}: 深度桶(2mm): {sorted_buckets}")
    for b in sorted_buckets[:5]:
        faces = depth_faces[b]
        # 计算该桶的平均半径
        radii = []
        for f in faces:
            fc = f.calc_center_median()
            dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
            radii.append(dxz * 1000)
        print(f"  {b}mm: {len(faces)}面, 半径{min(radii):.1f}-{max(radii):.1f} avg={sum(radii)/len(radii):.1f}mm")

# 输入模型眼睑边缘
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj_in = [o for o in bpy.data.objects if o.type == 'MESH'][0]
bm_in = bmesh.new(); bm_in.from_mesh(obj_in.data)

for side, center in [("L", cL), ("R", cR)]:
    lid_edges = []
    for e in bm_in.edges:
        ec = (e.verts[0].co + e.verts[1].co) / 2
        dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
        if not (0.005 < dxz < 0.025): continue
        if abs(ec.y - center.y) > 0.008: continue
        is_edge = False
        if len(e.link_faces) == 1:
            is_edge = True
        elif len(e.link_faces) == 2:
            f0, f1 = e.link_faces
            dot = f0.normal.dot(f1.normal)
            if dot < 0.5 and f0.normal.y * f1.normal.y < 0.3:
                is_edge = True
        if is_edge:
            lid_edges.append(ec)
    if lid_edges:
        xs = [e.x for e in lid_edges]; zs = [e.z for e in lid_edges]
        dxzs = [math.sqrt((e.x-center.x)**2 + (e.z-center.z)**2)*1000 for e in lid_edges]
        print(f"\n{side} 输入模型眼睑边缘: {len(lid_edges)}点, "
              f"x范围{(min(xs)-center.x)*1000:.1f}~{(max(xs)-center.x)*1000:.1f}mm "
              f"z范围{(min(zs)-center.z)*1000:.1f}~{(max(zs)-center.z)*1000:.1f}mm "
              f"半径{min(dxzs):.1f}~{max(dxzs):.1f}mm")
    else:
        print(f"\n{side}: 未找到眼睑边缘")
bm_in.free()
print("\n诊断完成")
