"""检查rim顶点的y坐标(深度)分布"""
import bpy, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)

for side, center in [("L", cL), ("R", cR)]:
    rim_verts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        depth = abs(v.co.y - center.y)
        if 0.003 < dxz < 0.018 and depth < 0.001:
            rim_verts.append(v)
    
    # 按y坐标排序
    rim_verts.sort(key=lambda v: v.co.y)
    print(f"\n{side}: rim顶点数={len(rim_verts)}")
    print(f"  y范围: {(rim_verts[0].co.y-center.y)*1000:+.2f} ~ {(rim_verts[-1].co.y-center.y)*1000:+.2f}mm")
    
    # 找出y坐标异常(偏离center.y)的顶点
    for v in rim_verts[:3]:
        dx = (v.co.x-center.x)*1000; dy = (v.co.y-center.y)*1000; dz = (v.co.z-center.z)*1000
        print(f"  最浅: ({dx:+.1f},{dy:+.1f},{dz:+.1f})mm")
    for v in rim_verts[-3:]:
        dx = (v.co.x-center.x)*1000; dy = (v.co.y-center.y)*1000; dz = (v.co.z-center.z)*1000
        print(f"  最深: ({dx:+.1f},{dy:+.1f},{dz:+.1f})mm")

bm.free()
print("\n诊断完成")
