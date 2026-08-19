"""检查贴图上 avg_uv 区域实际画的是什么 + 找下眼睑皮肤色的UV位置
深色根因: 碗面统一用avg_uv, 但该点落在贴图深色眼妆区
方案: 改用一个真正的"皮肤色"UV点(从眼睑下皮肤区采样)
"""
import bpy, bmesh, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]

tex_img = None
for mat in obj.data.materials:
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
W, H = tex_img.size
px = tex_img.pixels[:]
def sample(u, v):
    x = min(max(int(u*W), 0), W-1); y = min(max(int(v*H), 0), H-1)
    i = (y*W + x)*4
    return (px[i], px[i+1], px[i+2])

# 当前碗面用的avg_uv
AVG_L = (0.0793, 0.0632); AVG_R = (0.5786, 0.1021)
print("=== 当前avg_uv采样(深色根因) ===")
for name, (u, v) in [("L", AVG_L), ("R", AVG_R)]:
    c = sample(u, v)
    print(f"  {name} avg_uv=({u},{v}) RGB=({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}) 亮度={sum(c)/3:.2f}")

# 扫描avg_uv周围, 找皮肤色区域
print("\n=== avg_uv周围5x5网格采样(找皮肤色) ===")
for name, (cu, cv) in [("L", AVG_L), ("R", AVG_R)]:
    print(f"  {name} (中心={cu:.4f},{cv:.4f}):")
    for dv in range(-2, 3):
        row = ""
        for du in range(-2, 3):
            u = cu + du*0.004; v = cv + dv*0.004
            c = sample(u, v)
            br = sum(c)/3
            row += f"{br:.2f} "
        print(f"    v{cv+ (0.004*(dv-0)):+.3f}: {row}")

# 从下眼睑皮肤区(眼窝外下侧)采样真实皮肤UV
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active
print("\n=== 下眼睑皮肤区(眼窝外下侧)实际UV ===")
for side, center in [("L", cL), ("R", cR)]:
    skin_uvs = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = fc.x - center.x; dz = fc.z - center.z
        dxz = math.sqrt(dx*dx + dz*dz)
        # 下眼睑皮肤: 下方, 距离开口18-30mm(碗外皮肤)
        if dz < -0.010 and 0.018 < dxz < 0.030 and fc.y < -0.09:
            for l in f.loops:
                uv = l[uv_layer].uv
                skin_uvs.append((uv.x, uv.y))
    if skin_uvs:
        au = sum(u for u,v in skin_uvs)/len(skin_uvs)
        av = sum(v for u,v in skin_uvs)/len(skin_uvs)
        c = sample(au, av)
        print(f"  {side} 皮肤UV均值=({au:.4f},{av:.4f}) RGB=({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}) 亮度={sum(c)/3:.2f} ({len(skin_uvs)}loops)")
bm.free()
print("\n诊断完成")
