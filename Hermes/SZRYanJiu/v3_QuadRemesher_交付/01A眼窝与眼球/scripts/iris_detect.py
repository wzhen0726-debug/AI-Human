"""01_1眼窝制作 - 虹膜中心自动检测

原理: 高模贴图上画了眼睛, 虹膜是暗像素。取眼带区域顶点,
按UV采样贴图亮度, 取最暗的2%像素, 聚类取质心即虹膜中心。
"""
import bpy
import numpy as np
from eye_socket_config import *

def detect_iris_centers():
    """返回 (left_center, right_center) 局部坐标 numpy 数组"""
    obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
    mesh = obj.data
    nv = len(mesh.vertices)
    
    # 顶点坐标
    V = np.empty(nv*3, dtype=np.float32)
    mesh.vertices.foreach_get("co", V)
    V = V.reshape(nv,3)
    
    # UV坐标
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        raise RuntimeError("No active UV layer")
    loop_uv = np.empty(len(mesh.loops)*2, dtype=np.float32)
    uv_layer.data.foreach_get("uv", loop_uv)
    loop_uv = loop_uv.reshape(-1,2)
    # 顶点级UV: 取每个顶点第一个loop的UV
    vert_uv = np.empty((nv,2), dtype=np.float32)
    for i, loop in enumerate(mesh.loops):
        vi = loop.vertex_index
        vert_uv[vi] = loop_uv[i]
    
    # 贴图
    img = mesh.materials[0].node_tree.nodes.get("Image Texture").image
    tex = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)[:,:,:3]
    Ht, Wt = img.size[1], img.size[0]
    
    centers = {}
    for side, approx in [("L", IRIS_L), ("R", IRIS_R)]:
        approx = np.array(approx)
        d = np.linalg.norm(V - approx, axis=1)
        band = (d >= BAND_MIN) & (d < BAND_MAX)
        idx = np.where(band)[0]
        
        # 采样贴图亮度
        px = np.clip((vert_uv[idx,0]*(Wt-1)).astype(int), 0, Wt-1)
        py = np.clip((vert_uv[idx,1]*(Ht-1)).astype(int), 0, Ht-1)
        bright = tex[py,px].mean(axis=1)
        
        thr = np.percentile(bright, DARK_PCT)
        dark_idx = idx[bright <= thr]
        if len(dark_idx) < 10:
            raise RuntimeError(f"{side}: too few dark pixels ({len(dark_idx)})")
        
        center = V[dark_idx].mean(axis=0)
        centers[side] = center
        print(f"detect_iris {side}: n_dark={len(dark_idx)} center=({center[0]:.4f},{center[1]:.4f},{center[2]:.4f})")
    
    return centers["L"], centers["R"]
