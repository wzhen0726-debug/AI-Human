# -*- coding: utf-8 -*-
"""烘焙审核模块 v1 (2026-09-18 用户要求: 像03UV一样"跑几轮选最好", 参数全部由数据推导)

指标(全部无量纲/数据自参照):
  ① unfilled: 网格UV采样点的贴图【未填充率】—— 烘"空洞/未盖到"的直接度量
  ② dirty:    8px块中位色 相对 3×3邻域中位 的离群块占比(阈值=全局MAD×6, 由数据推导) —— "脏块"代理量
  ③ cv:       每面【纹素密度】(UV面积/3D面积) 的 std/中位 —— 与 03UV 同一口径(越小越均匀)

择优: 字典序 (unfilled, dirty, cv) 最小者 —— 不使用任何权重常数。
"""
import bpy
import numpy as np


def _uv_arrays(me):
    n = len(me.loops)
    uv = np.empty(n * 2, dtype=np.float32)
    me.uv_layers.active.uv.foreach_get("vector", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    a = np.zeros(len(me.polygons), np.float64)
    for i in range(len(me.polygons)):
        s = ls[i]; k = lt[i]
        p = uv[s:s + k]
        x, y = p[:, 0], p[:, 1]
        a[i] = 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
    return uv, ls, lt, a


def measure(png_path, low_poly, block=8):
    """对烘焙产物 PNG + 低模 测量 三项指标(不修改任何数据)。"""
    me = low_poly.data
    img = bpy.data.images.load(png_path, check_existing=False)
    W, H = int(img.size[0]), int(img.size[1])
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    uv, ls, lt, uva = _uv_arrays(me)
    cl = ls + lt // 2
    uvpts = np.concatenate([uv[cl], uv[ls]])          # 每面: 中心(近似) + 首角

    def _gather(uvp):
        u = np.clip((uvp[:, 0] % 1.0) * (W - 1), 0, W - 1).astype(np.int64)
        v = np.clip((uvp[:, 1] % 1.0) * (H - 1), 0, H - 1).astype(np.int64)
        return px[v, u]

    g = _gather(uvpts)
    # 未填充: alpha 有明显变化时用 alpha; 否则退回"纯黑"判据(烘焙未盖=纯黑)
    alpha = px[..., 3]
    if float(alpha.min()) < 0.5:
        unfilled = float((g[:, 3] < 0.5).mean())
    else:
        unfilled = float((g[:, :3].sum(axis=1) < 0.004).mean())
    # 脏块: 仅在填充区统计
    fill = (px[..., 3] >= 0.5) if float(alpha.min()) < 0.5 else (px[..., :3].sum(axis=-1) > 0.004)
    rgb = px[..., :3]
    hb, wb = H // block, W // block
    blk = rgb[:hb * block, :wb * block].reshape(hb, block, wb, block, 3).mean(axis=(1, 3))
    bfill = fill[:hb * block, :wb * block].reshape(hb, block, wb, block).mean(axis=(1, 3)) > 0.6
    stack = np.stack([np.roll(np.roll(blk, dy, 0), dx, 1)
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    med = np.median(stack, axis=0)
    dev = np.linalg.norm(blk - med, axis=-1)
    d = dev[bfill]
    if d.size:
        mad = float(np.median(np.abs(d - np.median(d))))
        dirty = float((d > max(6.0 * mad, 1e-6)).mean())
    else:
        dirty = 0.0
    # 密度CV(与03同口径)
    rat = np.array([uva[i] / p.area for i, p in enumerate(me.polygons)
                    if uva[i] > 1e-12 and p.area > 1e-12])
    cv = float(np.std(rat) / max(np.median(rat), 1e-12)) if rat.size else 0.0
    bpy.data.images.remove(img)
    return dict(unfilled=unfilled, dirty=dirty, cv=cv, W=W)


def better(a, b):
    """a 是否优于 b —— 字典序(unfilled → dirty → cv), 越小越好。"""
    return (a["unfilled"], a["dirty"], a["cv"]) < (b["unfilled"], b["dirty"], b["cv"])
