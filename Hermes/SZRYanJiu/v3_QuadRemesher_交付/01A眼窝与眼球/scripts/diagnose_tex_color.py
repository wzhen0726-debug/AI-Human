"""diagnose_tex_color: 定量诊断贴图在眼窝UV位置的实际颜色
1. 从 blend 找贴图 image + filepath
2. numpy 采样碗面 UV 点、倒角带 UV 范围、皮肤区 UV 的颜色
3. 定位黑斑块/白月牙的贴图采样根因
"""
import bpy, os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

# 1. 找贴图
img = None
mat_info = []
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                mat_info.append((m.name, n.name, n.image.name, n.image.filepath))
                if img is None:
                    img = n.image
print("材质贴图节点:")
for mi in mat_info:
    print("  ", mi)
if img is None:
    print("!! 无贴图 image")
    sys.exit()

print(f"\n使用贴图: {img.name} {img.size[0]}x{img.size[1]} filepath={img.filepath}")

# 2. 贴图像素 → numpy (H行, W列, RGBA)
W, H = img.size[0], img.size[1]
px = np.array(img.pixels[:]).reshape(H, W, 4)
print(f"pixels loaded: {px.shape}")

def sample_uv(u, v):
    """UV(u,v) -> RGB. Blender image.pixels: 第0行=v底部"""
    x = min(int(u * W), W - 1)
    y = min(int(v * H), H - 1)
    c = px[y, x, :3]
    return (round(float(c[0]), 3), round(float(c[1]), 3), round(float(c[2]), 3))

def region_stats(u0, u1, v0, v1, label):
    """统计UV区域的颜色分布"""
    x0, x1 = int(u0 * W), min(int(u1 * W), W - 1)
    y0, y1 = int(v0 * H), min(int(v1 * H), H - 1)
    if x1 <= x0 or y1 <= y0:
        print(f"  {label}: 空区域")
        return
    reg = px[y0:y1+1, x0:x1+1, :3]
    lum = reg.mean(axis=2)
    print(f"  {label}: 亮min={lum.min():.3f} max={lum.max():.3f} mean={lum.mean():.3f} "
          f"RGB均值=({reg[:,:,0].mean():.3f},{reg[:,:,1].mean():.3f},{reg[:,:,2].mean():.3f}) "
          f"采样[{x0}:{x1},{y0}:{y1}]")

# 3. 眼窝相关 UV 位置采样
print("\n=== 碗面均匀 UV 采样 ===")
for label, (u, v) in [("L碗面(0.0793,0.0632)", (0.0793, 0.0632)),
                      ("R碗面(0.5786,0.1021)", (0.5786, 0.1021))]:
    print(f"  {label}: RGB={sample_uv(u, v)}")

print("\n=== 倒角带 UV 范围采样 (L u=[0.0732,0.0823] v=[0.0635,0.0784]) ===")
region_stats(0.0732, 0.0823, 0.0635, 0.0784, "L倒角带")

print("\n=== 周边皮肤 UV 采样 ===")
region_stats(0.0725, 0.0867, 0.05, 0.10, "L眼周皮肤区")
region_stats(0.5752, 0.5923, 0.08, 0.13, "R眼周皮肤区")

# 4. 全贴图亮度分布 + 最亮/最暗区
print("\n=== 全贴图亮度分布 ===")
lum_all = px[:, :, :3].mean(axis=2)
print(f"  全图: min={lum_all.min():.3f} max={lum_all.max():.3f} mean={lum_all.mean():.3f}")
# 眼白区域检测: 亮度>0.8 的连通区域位置
bright = lum_all > 0.8
print(f"  亮度>0.8像素占比: {bright.mean()*100:.1f}%")
if bright.any():
    ys, xs = np.where(bright)
    # 找最密集的亮区中心
    print(f"  亮区u范围: [{xs.min()/W:.4f}, {xs.max()/W:.4f}] v范围: [{ys.min()/H:.4f}, {ys.max()/H:.4f}]")

# 5. 输出 blend 里碗面/倒角带实际 loop UV 集合采样(直接从网格读)
print("\n=== 从网格直接采样眼窝区 loop UV → 贴图颜色 ===")
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
from mathutils import Vector
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active
if uv_layer is None:
    print("  !! 网格无UV层")
else:
    for side, center in [("L", cL), ("R", cR)]:
        # 眼窝碗面区域 loop: 距眼中心 xz < 15mm 且 y 比眼中心深(朝头内)
        bowl_loops = []
        rim_loops = []
        for f in bm.faces:
            for loop in f.loops:
                co = loop.vert.co
                dxz = ((co.x - center.x)**2 + (co.z - center.z)**2) ** 0.5
                if dxz < 0.020:
                    if co.y > center.y + 0.002:  # 碗内(深入头部)
                        bowl_loops.append(loop)
                    elif dxz < 0.006:  # 中心附近
                        rim_loops.append(loop)
        colors = []
        for loop in bowl_loops[:500]:
            u, v = loop[uv_layer].uv
            colors.append(sample_uv(u, v))
        if colors:
            arr = np.array(colors)
            lum = arr.mean(axis=1)
            print(f"  {side} 碗面{len(bowl_loops)}loops(采样{len(colors)}): "
                  f"亮度min={lum.min():.3f} max={lum.max():.3f} mean={lum.mean():.3f}")
            dark_pct = (lum < 0.15).mean() * 100
            bright_pct = (lum > 0.7).mean() * 100
            print(f"    暗(<0.15)占{dark_pct:.0f}%  亮(>0.7)占{bright_pct:.0f}%")
bm.free()

print("\n诊断完成")
