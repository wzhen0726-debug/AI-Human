# -*- coding: utf-8 -*-
"""网格射线探针 δy: 对比两份 blend 在眼窝区域的表面深度差异(拓扑无关, 两版拓扑可不同)
用法:
  blender -b --factory-startup --python grid_probe_delta.py -- <blendA> <blendB> [out_png] [cx_mm] [cz_mm]
输出:
  1) Δy 文本网格(行=dz mm, 列=x mm), Δy = B - A
  2) 每行 min/max/mean → 定位"哪几行动了、动多少"
  3) 热力图 png(红=更深/靠后, 蓝=更浅/靠前)
符号约定(本项目): y 越负越靠前 → Δy>0 = B 更靠后(=更深), <0 = 更靠前(=更浅)。
标错号 = 把方向读反; 解读前先核对。
默认轴线按当前资产(右眼中心 x=35mm, z=1671.2mm), 换模型/换眼时传 cx cz。
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) < 2:
    print("用法: ... -- <blendA> <blendB> [out_png] [cx_mm] [cz_mm]", flush=True)
    raise SystemExit(1)
A_path, B_path = args[0], args[1]
out_png = args[2] if len(args) > 2 else os.path.join(os.path.dirname(A_path), "grid_delta.png")
CX = float(args[3]) / 1000.0 if len(args) > 3 else 0.035
CZ = float(args[4]) / 1000.0 if len(args) > 4 else 1.6712
XS = np.arange(CX - 0.017, CX + 0.0261, 0.002)   # 18..61mm 带
DZS = np.arange(-10, 8.1, 1.0)                    # 眼心上下 ±10mm


def probe(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    obj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    g = np.full((len(DZS), len(XS)), np.nan)
    for i, dz in enumerate(DZS):
        for j, x in enumerate(XS):
            hit, loc, nrm, idx = ev.ray_cast(Vector((x, -0.15, CZ + dz / 1000.0)), Vector((0, 1, 0)))
            if hit:
                g[i, j] = loc.y * 1000.0
    return g


GA = probe(A_path)
GB = probe(B_path)
D = GB - GA

print("Δy = B - A (mm); Δy>0 = B 更靠后(=更深), <0 = 更靠前(=更浅)", flush=True)
print("列 = x(mm): " + " ".join(f"{x*1000:6.0f}" for x in XS), flush=True)
for i, dz in enumerate(DZS):
    cells = [f"{D[i, j]:+6.1f}" if np.isfinite(D[i, j]) else "   -- " for j in range(len(XS))]
    print(f"dz={dz:+3.0f}mm: " + " ".join(cells), flush=True)

print("\n每行统计(定位哪几行动了):", flush=True)
for i, dz in enumerate(DZS):
    row = D[i]
    if np.isfinite(row).sum() == 0:
        continue
    print(f"  dz={dz:+.0f}mm: 浅{np.nanmin(row):+.1f}@{XS[int(np.nanargmin(row))]*1000:.0f}  "
          f"深{np.nanmax(row):+.1f}@{XS[int(np.nanargmax(row))]*1000:.0f}  均值{np.nanmean(row):+.2f}", flush=True)

try:
    from PIL import Image, ImageDraw
    cw = ch = 14
    W, H = cw * len(XS), ch * len(DZS)
    im = Image.new("RGB", (W + 96, H + 40), (25, 25, 25))
    dr = ImageDraw.Draw(im)

    def col(v):
        if not np.isfinite(v):
            return (60, 60, 60)
        t = max(-1.0, min(1.0, v / 5.0))
        if t >= 0:
            return (int(80 + 175 * t), int(80 * (1 - t)), int(80 * (1 - t)))
        t = -t
        return (int(80 * (1 - t)), int(80 * (1 - t)), int(80 + 175 * t))

    for i, dz in enumerate(DZS):
        yy = H - ch * (i + 1) + 30
        for j in range(len(XS)):
            dr.rectangle([96 + cw * j, yy, 96 + cw * (j + 1) - 1, yy + ch - 1], fill=col(D[i, j]))
        dr.text((6, yy + 3), f"dz{dz:+.0f}", fill=(220, 220, 220))
    for j, x in enumerate(XS):
        if int(x * 1000) % 8 == 0:
            dr.text((96 + cw * j, 8), f"{int(x*1000)}", fill=(220, 220, 220))
    dr.text((6, 8), "x(mm)", fill=(220, 220, 220))
    dr.text((6, 22), "红=更深(后) 蓝=更浅(前)", fill=(200, 200, 120))
    im.save(out_png)
    print("HEAT:", out_png, flush=True)
except Exception as e:
    print("热力图跳过(PIL 不可用):", e, flush=True)
print("GRID_PROBE_DONE", flush=True)
