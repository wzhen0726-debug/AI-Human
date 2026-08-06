"""debug: 用贴图采样实测eye GLB瞳孔在局部坐标的真实方向
方法: 每顶点取UV采样贴图颜色, 最暗1.5%顶点=瞳孔+虹膜区, 其质心相对球心方向=瞳孔朝向"""
import bpy, sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.import_scene.gltf(filepath=EYE_GLB)
eyes = [o for o in bpy.context.selected_objects if o.type == 'MESH']

for o in eyes:
    mesh = o.data
    # 找贴图
    img = None
    for mat in mesh.materials:
        if not mat or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                break
        if img:
            break
    if img is None:
        print(f"{o.name}: NO TEXTURE")
        continue
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)  # row0 = v=0(bottom)

    # 每顶点平均UV
    uv = mesh.uv_layers.active.data
    nv = len(mesh.vertices)
    uv_sum = np.zeros((nv, 2), dtype=np.float64)
    cnt = np.zeros(nv, dtype=np.int32)
    for loop in mesh.loops:
        uv_sum[loop.vertex_index] += uv[loop.index].uv
        cnt[loop.vertex_index] += 1
    uv_avg = uv_sum / np.maximum(cnt, 1)[:, None]

    u = np.clip((uv_avg[:, 0] % 1.0) * W, 0, W - 1).astype(int)
    v = np.clip((uv_avg[:, 1] % 1.0) * H, 0, H - 1).astype(int)
    colors = px[v, u, :3]
    lum = colors.mean(1)
    thr = np.percentile(lum, 1.5)
    dark = np.where(lum <= thr)[0]

    Vall = np.array([mv.co[:] for mv in mesh.vertices], dtype=np.float64)
    sphere_c = (Vall.min(0) + Vall.max(0)) / 2
    pupil_c = Vall[dark].mean(0)
    d = pupil_c - sphere_c
    d = d / np.linalg.norm(d)
    print(f"=== {o.name} ===")
    print(f"  texture: {img.name} {W}x{H}, dark_verts={len(dark)}")
    print(f"  pupil_center_local={np.round(pupil_c,4)}")
    print(f"  PUPIL_LOCAL_DIR = ({d[0]:.3f}, {d[1]:.3f}, {d[2]:.3f})")
