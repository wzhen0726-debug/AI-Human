"""diagnose_rim_vs_eyeball: rim开口 vs 眼球截面
问题: vision报"眼裂偏宽偏圆、巩膜暴露过多、内外眼角不包裹眼球"
诊断: 1) rim开口实际宽高(在rim平面y处的截面)
      2) 眼球半径(14.5mm)在rim平面的弦长
      3) 开口宽/眼球弦长 比例 — 若开口>眼球弦长, 巩膜会暴露
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]
eyeL = [o for o in bpy.data.objects if 'Eye_R' in o.name][0]
eyeR = [o for o in bpy.data.objects if 'Eye_L' in o.name][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

bm = bmesh.new(); bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()
V = np.array([v.co for v in bm.verts])

for side, center, eye_obj in [("L", cL, eyeL), ("R", cR, eyeR)]:
    eye_center = Vector(eye_obj.matrix_world.translation)
    # rim平面: 眼窝开口y位置(碗唇缘)
    dxz = np.sqrt((V[:,0]-center.x)**2 + (V[:,2]-center.z)**2)
    y_ok = (V[:,1] > -0.15) & (V[:,1] < -0.05)
    sel = (dxz < 0.016) & y_ok
    if sel.sum() == 0: continue
    pole_y = V[sel, 1].max()
    rim_y = pole_y - 0.006  # CUP_DEPTH
    
    # rim开口顶点(在rim平面±1mm)
    rim_mask = (dxz < 0.016) & (np.abs(V[:,1] - rim_y) < 0.001) & y_ok
    if rim_mask.sum() < 3:
        print(f"{side}: rim顶点不足"); continue
    rim_v = V[rim_mask]
    # 开口宽高(xz平面)
    x_span = rim_v[:,0].max() - rim_v[:,0].min()
    z_span = rim_v[:,2].max() - rim_v[:,2].min()
    
    # 眼球在rim平面的截面: 球半径r, 球心y, 截面y=rim_y
    # 截面圆半径 = sqrt(r^2 - (rim_y - eye_center.y)^2)
    dy = rim_y - eye_center.y
    if abs(dy) < EYE_RADIUS:
        section_r = math.sqrt(EYE_RADIUS**2 - dy**2)
    else:
        section_r = 0
    
    print(f"\n=== {side}眼 rim开口 vs 眼球截面 ===")
    print(f"  rim平面y={rim_y:.4f} (pole_y={pole_y:.4f})")
    print(f"  眼球球心y={eye_center.y:.4f} (球心在rim平面{'后' if eye_center.y>rim_y else '前'} {abs(eye_center.y-rim_y)*1000:.1f}mm)")
    print(f"  rim开口宽={x_span*1000:.1f}mm 高={z_span*1000:.1f}mm (宽高比{x_span/max(z_span,0.0001):.1f}:1)")
    print(f"  眼球在rim平面弦长(宽)={section_r*2*1000:.1f}mm")
    print(f"  开口宽/眼球弦长 = {x_span/(section_r*2):.2f} (>1=巩膜暴露, 理想≈0.9-1.0)")
    print(f"  开口高/眼球弦长 = {z_span/(section_r*2):.2f}")
bm.free()
print("\n诊断完成")
