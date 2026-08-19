"""diagnose_eyelid_uv2: 检查下眼睑面UV采样到的贴图实际颜色
深棕斑块 = UV位置正确但落在贴图的深色区(眉毛/眼线/阴影)
"""
import bpy, bmesh, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]

# 找贴图
tex_img = None
for mat in obj.data.materials:
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
if not tex_img:
    print("未找到贴图"); sys.exit()
W, H = tex_img.size
print(f"贴图: {tex_img.name} {W}x{H}")
px = tex_img.pixels[:]

def sample(u, v):
    x = min(max(int(u*W), 0), W-1); y = min(max(int(v*H), 0), H-1)
    i = (y*W + x)*4
    return (px[i], px[i+1], px[i+2])

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active

# 扫描下眼睑区(斑块位置: 下眼睑dz<0, 内眼角到外眼角)
for side, center in [("L", cL), ("R", cR)]:
    print(f"\n=== {side}眼下眼睑区 UV→贴图颜色 ===")
    samples = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = fc.x - center.x; dz = fc.z - center.z
        dxz = math.sqrt(dx*dx + dz*dz)
        if dz < -0.001 and 0.003 < dxz < 0.018 and fc.y < -0.09:
            uvs = [l[uv_layer].uv.copy() for l in f.loops]
            au = sum(uv.x for uv in uvs)/len(uvs)
            av = sum(uv.y for uv in uvs)/len(uvs)
            col = sample(au, av)
            bright = sum(col)/3
            samples.append((dx*1000, dz*1000, au, av, col, bright))
    # 按亮度排序找最暗的(采样到深色的)
    samples.sort(key=lambda s: s[5])
    print(f"  共{len(samples)}面, 最暗的8个(采样到深色):")
    for dx, dz, u, v, col, br in samples[:8]:
        print(f"    位置({dx:+.1f},{dz:+.1f})mm UV=({u:.4f},{v:.4f}) 贴图RGB=({col[0]:.2f},{col[1]:.2f},{col[2]:.2f}) 亮度={br:.2f}")
    print(f"  最亮的8个(正常皮肤):")
    for dx, dz, u, v, col, br in samples[-8:]:
        print(f"    位置({dx:+.1f},{dz:+.1f})mm UV=({u:.4f},{v:.4f}) 贴图RGB=({col[0]:.2f},{col[1]:.2f},{col[2]:.2f}) 亮度={br:.2f}")
    # 统计暗面数量(亮度<0.35=深棕)
    dark_n = sum(1 for s in samples if s[5] < 0.35)
    print(f"  深色面(亮度<0.35): {dark_n}/{len(samples)}")
bm.free()
print("\n诊断完成")
