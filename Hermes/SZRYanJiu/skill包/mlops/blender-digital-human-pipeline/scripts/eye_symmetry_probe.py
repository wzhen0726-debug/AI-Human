# -*- coding: utf-8 -*-
"""左右眼对称核查 — 数秒出数, 先排除真错误再答复"两眼观感不一致".

用法:
  blender -b --factory-startup --python eye_symmetry_probe.py -- <blend路径> [名字包含串(默认 Eye)]

输出四块:
  1) 每只眼球: 世界中心 / PCA角膜轴(翻正朝 -y) / 与正前夹角 / 半径(均值+最大=角膜顶点)
  2) 左右镜像: 中心镜像偏差(mm) + 角膜轴镜像夹角(deg) —— 合格都 ≈0
  3) 两眼球 UV 对照: 同向 vs 镜像(u→1-u) 各自最大差 —— 判定 UV 是否已镜像
  4) 两眼球所挂材质 diff: 节点/贴图(文件名+colorspace)/BSDF 关键值/连线(按类型规范化, 忽略 .001 后缀)

判读: 几何≈0 + 材质一致 + UV 未镜像(虹膜图案自然重复) → 视口"一眼一样"= 光照镜面高光差异(物理必然),
不要为光照差异动模型; 几何/材质有真差异 → 先修模型再答复。
"""
import os
import sys

import bpy
import numpy as np


def parse_args():
    if "--" in sys.argv:
        rest = sys.argv[sys.argv.index("--") + 1:]
        if rest:
            return rest[0], (rest[1] if len(rest) > 1 else "Eye")
    raise SystemExit("用法: blender -b --python eye_symmetry_probe.py -- <blend> [NamePattern]")


def main():
    blend, pat = parse_args()
    if not os.path.exists(blend):
        raise SystemExit("文件不存在: %s" % blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    eyes = sorted([o for o in bpy.data.objects
                   if o.type == 'MESH' and pat in o.name], key=lambda o: o.name)
    print("== 眼球对象: %s ==" % [e.name for e in eyes], flush=True)
    info = {}
    for e in eyes:
        Mb = np.array(e.matrix_world)
        vs = np.empty((len(e.data.vertices), 3))
        e.data.vertices.foreach_get("co", vs.ravel())
        vw = vs @ Mb[:3, :3].T + Mb[:3, 3]
        c = vw.mean(axis=0)
        X = vw - c
        _w, V = np.linalg.eigh(X.T @ X)
        axis = V[:, -1]                      # 最大方差方向 = 前后轴
        proj = X @ axis
        if abs(proj.min()) > abs(proj.max()):
            axis = -axis
        if axis[1] > 0:                      # 翻正: 角膜朝 -y(前方)
            axis = -axis
        ang = float(np.degrees(np.arccos(np.clip(np.dot(axis, [0.0, -1.0, 0.0]), -1.0, 1.0))))
        rr = np.linalg.norm(X, axis=1)
        info[e.name] = (c, axis, ang)
        print("%s: 中心=(%+.2f,%+.2f,%+.2f)mm 与正前夹角=%.2f° 半径均值=%.2fmm 最大=%.2fmm"
              % (e.name, c[0] * 1000, c[1] * 1000, c[2] * 1000, ang,
                 rr.mean() * 1000, rr.max() * 1000), flush=True)

    names = list(info)
    nL = next((n for n in names if "L" in n), None)
    nR = next((n for n in names if "R" in n), None)
    if len(names) == 2 and nL and nR:
        cL, aL, _ = info[nL]
        cR, aR, _ = info[nR]
        cLm = cL * np.array([-1.0, 1.0, 1.0])   # 镜像
        aLm = aL * np.array([-1.0, 1.0, 1.0])
        dpos = float(np.linalg.norm(cLm - cR)) * 1000
        da = float(np.degrees(np.arccos(np.clip(
            np.dot(aLm / np.linalg.norm(aLm), aR / np.linalg.norm(aR)), -1.0, 1.0))))
        print("镜像核对: 中心镜像偏差=%.3fmm 角膜轴镜像夹角=%.3f°" % (dpos, da), flush=True)

    # UV 同向 vs 镜像
    uvs = {}
    for e in eyes:
        me = e.data
        if me.uv_layers.active is None:
            continue
        arr = np.empty(len(me.uv_layers.active.data) * 2)
        me.uv_layers.active.data.foreach_get("uv", arr)
        uvs[e.name] = arr.reshape(-1, 2)
    if len(uvs) == 2:
        a, b = list(uvs.values())
        if len(a) == len(b):
            same = float(np.abs(a - b).max())
            bm = b.copy()
            bm[:, 0] = 1.0 - bm[:, 0]
            mir = float(np.abs(a - bm).max())
            print("UV对照: 同向最大差=%.5f 镜像(u→1-u)最大差=%.5f → %s"
                  % (same, mir, "两UV一致(未镜像)" if same < mir else "两UV为镜像关系"), flush=True)

    # 材质 diff(按节点类型/贴图文件规范化, 忽略自动 .001 后缀差异)
    seen = {}
    for e in eyes:
        for slot in e.material_slots:
            m = slot.material
            if m and m.name not in seen:
                seen[m.name] = m
    sig = {}
    for name, m in sorted(seen.items()):
        lines = []
        if m.use_nodes:
            for nd in m.node_tree.nodes:
                extra = ""
                if nd.type == 'TEX_IMAGE' and nd.image:
                    extra = " img=%s cs=%s" % (os.path.basename(nd.image.filepath or nd.image.name),
                                               nd.image.colorspace_settings.name)
                lines.append("  node %s%s" % (nd.type, extra))
                if nd.type == 'BSDF_PRINCIPLED':
                    vals = []
                    for k in ("Roughness", "Metallic", "IOR", "Alpha"):
                        inp = nd.inputs.get(k)
                        if inp is not None:
                            v = inp.default_value
                            vals.append("%s=%s" % (k, tuple(round(x, 3) for x in v)
                                                   if hasattr(v, "__len__") else round(float(v), 3)))
                    lines.append("    bsdf: " + " ".join(vals))
            for l in m.node_tree.links:
                lines.append("  link %s.%s -> %s.%s"
                             % (l.from_node.type, l.from_socket.name, l.to_node.type, l.to_socket.name))
        else:
            lines.append("  (无节点)")
        sig[name] = "\n".join(lines)
    for name, s in sig.items():
        print("== 材质 %s ==" % name)
        print(s)
    if len(sig) == 2:
        v = list(sig.values())
        print("材质diff: %s" % ("完全一致" if v[0] == v[1] else "有差异(见上, 逐行比对)"), flush=True)
    print("EYE_SYMMETRY_DONE", flush=True)


main()
