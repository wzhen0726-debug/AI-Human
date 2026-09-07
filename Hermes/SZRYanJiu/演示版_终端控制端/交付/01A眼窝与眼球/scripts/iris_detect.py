"""01A眼窝与眼球 - 虹膜中心自动检测 (v2, 2026-08-06重写)

原理: 高模贴图上画了眼睛, 瞳孔是暗像素. 但暗像素里混着内眼角/睫毛/卧蚕暗斑,
直接取暗像素质心会被拉偏(实测质心偏向鼻梁, 眼间距被测小42%).

v2算法(有物理依据, 不再靠猜):
1. 全脸眼带(z 1.60~1.70, y<-0.08前侧, |x|<0.08), 不靠种子点
2. 按鼻梁中线x=0分左右两半
3. 每半取最暗10%像素, 在x-z平面K-means分2簇 -> 外侧簇(|x|大)是真瞳孔区,
   内侧簇是内眼角/下睑暗斑
4. 外侧簇里再取最暗30%(瞳孔比眼睑阴影更暗), 质心即瞳孔中心

实测验证(vision标定瞳孔像素): 左眼偏差+9px, 右眼-3px (原算法79/68px).
眼间距从46mm(偏小)修正到71.7mm(与vision实测偏宽比例一致).
"""
import bpy
import numpy as np
from eye_socket_config import *


def _kmeans2(pts, seed=0, iters=50):
    """2簇K-means, 输入Nx2点, 返回(labels, centers)"""
    rng = np.random.default_rng(seed)
    c = pts[rng.choice(len(pts), 2, replace=False)].copy()
    for _ in range(iters):
        d = ((pts[:, None, :] - c[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        nc = np.array([pts[lab == k].mean(0) if (lab == k).any() else c[k] for k in range(2)])
        if np.allclose(nc, c):
            break
        c = nc
    return lab, c


def detect_iris_centers():
    """返回 (left_center, right_center) 局部坐标 numpy 数组"""
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    mesh = obj.data
    nv = len(mesh.vertices)

    # 顶点坐标
    V = np.empty(nv * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", V)
    V = V.reshape(nv, 3)

    # UV坐标
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        raise RuntimeError("No active UV layer")
    loop_uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    uv_layer.data.foreach_get("uv", loop_uv)
    loop_uv = loop_uv.reshape(-1, 2)
    vert_uv = np.empty((nv, 2), dtype=np.float32)
    for i, loop in enumerate(mesh.loops):
        vert_uv[loop.vertex_index] = loop_uv[i]

    # 贴图
    img = mesh.materials[0].node_tree.nodes.get("Image Texture").image
    tex = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)[:, :, :3]
    Ht, Wt = img.size[1], img.size[0]

    # 全脸眼带(不依赖种子点)
    mask = ((V[:, 2] > EYE_BAND_Z_MIN) & (V[:, 2] < EYE_BAND_Z_MAX)
            & (V[:, 1] < EYE_BAND_Y_MAX) & (np.abs(V[:, 0]) < EYE_BAND_X_MAX))
    idx = np.where(mask)[0]
    px = np.clip((vert_uv[idx, 0] * (Wt - 1)).astype(int), 0, Wt - 1)
    py = np.clip((vert_uv[idx, 1] * (Ht - 1)).astype(int), 0, Ht - 1)
    bright_all = tex[py, px].mean(axis=1)

    centers = {}
    for side, sgn in [("L", -1.0), ("R", 1.0)]:
        # 按鼻梁中线分半
        sel = (V[idx, 0] * sgn) > 0
        sub_idx = idx[sel]
        sub_b = bright_all[sel]
        if len(sub_idx) < 10:
            raise RuntimeError(f"{side}: too few band verts ({len(sub_idx)})")

        # 该侧最暗 DARK_PCT%
        thr = np.percentile(sub_b, DARK_PCT)
        dark_mask = sub_b <= thr
        pts3 = V[sub_idx[dark_mask]]
        br = sub_b[dark_mask]

        # x-z平面K-means分2簇, 选外侧簇(|x|大=离鼻梁远=真瞳孔)
        lab, cent = _kmeans2(pts3[:, [0, 2]])
        outer_k = 0 if abs(cent[0][0]) > abs(cent[1][0]) else 1
        outer = pts3[lab == outer_k]
        outer_b = br[lab == outer_k]

        # 外侧簇里最暗 PUPIL_CORE_PCT% (瞳孔比眼睑阴影更暗)
        core_thr = np.percentile(outer_b, PUPIL_CORE_PCT)
        core = outer[outer_b <= core_thr]
        center = core.mean(axis=0)
        centers[side] = center
        print(f"detect_iris {side}: band={len(sub_idx)} dark={dark_mask.sum()} "
              f"outer={len(outer)} core={len(core)} center=({center[0]:.4f},{center[1]:.4f},{center[2]:.4f})")

    return centers["L"], centers["R"]
