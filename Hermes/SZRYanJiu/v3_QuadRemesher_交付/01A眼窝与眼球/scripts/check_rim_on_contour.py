"""检查rim顶点是否被拉到3DDFA轮廓上"""
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

# 找眼窝区最浅的一圈顶点(y≈center.y)
for side, center in [("L", cL), ("R", cR)]:
    rim_verts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        depth = abs(v.co.y - center.y)
        if 0.003 < dxz < 0.018 and depth < 0.001:
            rim_verts.append(v.co.copy())
    
    # 3DDFA轮廓
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as f:
        dd = json.load(f)
    rim_3ddfa = [Vector((r[0], r[1], r[2])) for r in dd[side]["rim_3d"] if r is not None]
    
    # 检查rim顶点是否在3DDFA轮廓上
    on_contour = 0
    off_contour = 0
    for v in rim_verts:
        best = min((v - p).length for p in rim_3ddfa)
        if best < 0.001:  # 1mm内=在轮廓上
            on_contour += 1
        else:
            off_contour += 1
    
    print(f"{side}: rim顶点={len(rim_verts)}, 在轮廓上={on_contour}, 偏离={off_contour} ({off_contour/len(rim_verts)*100:.0f}%)")
    
    # 找出偏离最远的顶点
    dists = []
    for v in rim_verts:
        best = min((v - p).length for p in rim_3ddfa)
        dists.append((best*1000, v))
    dists.sort(reverse=True)
    print(f"  最偏离的5个顶点:")
    for d, v in dists[:5]:
        dx = (v.x-center.x)*1000; dz = (v.z-center.z)*1000
        print(f"    ({dx:+.1f},{dz:+.1f})mm 偏离={d:.1f}mm")

bm.free()
print("\n诊断完成")
