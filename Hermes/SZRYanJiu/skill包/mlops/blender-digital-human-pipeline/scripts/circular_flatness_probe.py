# -*- coding: utf-8 -*-
"""圈级平坦度探针: 对比两份 blend 在眼窝"同一半径圆"上的表面深度波动
用途: 验证/反推"逐圈打平"类改动 —— 打平后同圈 y 波动应系统性变小, 而各圈均值基本不变。
用法:
  blender -b --factory-startup --python circular_flatness_probe.py -- <blendA> <blendB> [cx_mm] [cz_mm] [radii_csv]
注: 从 y=-0.15 沿 +Y 打首个命中, 只统计 y<-50mm 的命中(排除后脑/背面)。
符号约定(本项目): y 越负越靠前。
"""
import bpy, sys, math
import numpy as np
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) < 2:
    print("用法: ... -- <blendA> <blendB> [cx_mm] [cz_mm] [radii_csv]", flush=True)
    raise SystemExit(1)
CX = float(args[2]) / 1000.0 if len(args) > 2 else 0.035
CZ = float(args[3]) / 1000.0 if len(args) > 3 else 1.6712
RADII = [float(v) for v in args[4].split(",")] if len(args) > 4 else [9, 7, 5, 3, 2]


def probe(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    obj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    out = {}
    for r_mm in RADII:
        ys = []
        for k in range(24):
            th = 2 * math.pi * k / 24
            x = CX + r_mm / 1000.0 * math.cos(th)
            z = CZ + r_mm / 1000.0 * math.sin(th)
            hit, loc, nrm, idx = ev.ray_cast(Vector((x, -0.15, z)), Vector((0, 1, 0)))
            if hit and loc.y < -0.05:
                ys.append(loc.y * 1000.0)
        out[r_mm] = ys
    return out


A = probe(args[0])
B = probe(args[1])
print("圈级平坦度(同一半径圆上 24 点): std 越小 = 该圈越平", flush=True)
print(f"{'r(mm)':>6} | {'A: n / 均值 / std / 幅度':>26} | {'B: n / 均值 / std / 幅度':>26}", flush=True)
for r_mm in RADII:
    line = f"{r_mm:>6.0f} |"
    for g in (A[r_mm], B[r_mm]):
        if len(g) < 12:
            line += f" {'命中不足(' + str(len(g)) + ')':>26} |"
        else:
            a = np.array(g)
            line += f" {len(a):>3d} {a.mean():>8.2f} {a.std():>6.2f} {a.max() - a.min():>6.1f} |"
    print(line, flush=True)
print("CIRC_PROBE_DONE", flush=True)
