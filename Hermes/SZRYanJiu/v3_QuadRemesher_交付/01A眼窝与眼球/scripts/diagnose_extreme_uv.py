"""diagnose_extreme_uv: 找眼窝区UV落在极端值(0/1附近)的loop
根因假设: 迭代日志显示UV范围u=[0.0000,1.0000], 极端UV采样贴图角落→白弧/黑斑
1. 统计眼窝区loop UV分布, 找极端UV loop的空间位置
2. 采样贴图四角颜色
3. 报告材质 roughness/specular (排查高光假设)
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

# 贴图
img = None
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                img = n.image
if img:
    W, H = img.size[0], img.size[1]
    px = np.array(img.pixels[:]).reshape(H, W, 4)
    def sample_uv(u, v):
        x = min(max(int(u * W), 0), W - 1)
        y = min(max(int(v * H), 0), H - 1)
        c = px[y, x, :3]
        return (round(float(c[0]),3), round(float(c[1]),3), round(float(c[2]),3))
    print("=== 贴图四角颜色 ===")
    for name, (u, v) in [("左下(0,0)", (0,0)), ("右下(1,0)", (1,0)),
                         ("左上(0,1)", (0,1)), ("右上(1,1)", (1,1)),
                         ("中心(0.5,0.5)", (0.5,0.5))]:
        print(f"  {name}: RGB={sample_uv(u, v)}")

# 材质参数
print("\n=== 材质 BSDF 参数 ===")
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                r = m.node_tree.nodes.get
                print(f"  [{m.name}] roughness={n.inputs['Roughness'].default_value:.3f} "
                      f"specular={n.inputs['Specular IOR Level'].default_value if 'Specular IOR Level' in n.inputs else n.inputs.get('Specular', None) and n.inputs['Specular'].default_value} "
                      f"metallic={n.inputs['Metallic'].default_value}")

# 眼窝区 loop UV 分布
import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active

print("\n=== 眼窝区(dxz<22mm) loop UV 极端值统计 ===")
for side, center in [("L", cL), ("R", cR)]:
    n_total = 0; extremes = []
    uv_us = []; uv_vs = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = ((fc.x-center.x)**2 + (fc.z-center.z)**2) ** 0.5
        if dxz >= 0.022: continue
        for loop in f.loops:
            n_total += 1
            u, v = loop[uv_layer].uv
            uv_us.append(u); uv_vs.append(v)
            if u < 0.02 or u > 0.98 or v < 0.02 or v > 0.98:
                co = loop.vert.co
                extremes.append((round(u,3), round(v,3),
                                 round((co.x-center.x)*1000,1), round((co.y-center.y)*1000,1),
                                 round((co.z-center.z)*1000,1)))
    uv_us = np.array(uv_us); uv_vs = np.array(uv_vs)
    print(f"  {side}: loops={n_total}, u=[{uv_us.min():.4f},{uv_us.max():.4f}] "
          f"v=[{uv_vs.min():.4f},{uv_vs.max():.4f}], 极端UV loop={len(extremes)}")
    # 极端loop按位置分类: 在碗内(y>+2mm)还是边缘带
    for u, v, dx, dy, dz in extremes[:15]:
        loc = "碗内" if dy > 2 else ("边缘" if dy > -3 else "皮肤前")
        col = sample_uv(u, v) if img else "?"
        print(f"    uv=({u},{v}) 偏移(mm)=({dx},{dy},{dz}) [{loc}] 采样色={col}")
bm.free()
print("\n诊断完成")
