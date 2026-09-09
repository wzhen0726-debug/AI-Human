# -*- coding: utf-8 -*-
"""同源对比: 当前02(材质分区修复版) vs A配置备份(角度检测硬边) vs D污染版逻辑.
一次加载高模, 对比两个低模的 rim区双向Chamfer + 折角中位数.
判据自洽(PAD/折角定义两边完全一致), 数字才可比 — 不与历史脚本的绝对值比.

性能: bbox预筛+分块防广播爆内存; KDTree.find取[2]=距离; 折角用中位数避退化面离群.
"""
import bpy, os, json, sys
import numpy as np
import bmesh
from mathutils.kdtree import KDTree

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
HI = os.path.join(D, "交付", "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
LOs = {
    "新(材质分区修复)": os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k.blend"),
    "A备份(角度硬边)":   os.path.join(D, "交付", "02QuadRemesher拓扑", "_backup_20260908_A配置", "02_qr_150k.blend"),
}
cont = json.load(open(os.path.join(D, "交付", "01A眼窝与眼球", "screenshots", "3ddfa",
                                   "eyelid_contour_manual.json"), encoding="utf-8"))
rim = np.vstack([np.array(cont[s]["rim_3d"]) for s in ("L", "R")])
PAD = 0.015
S0 = rim[None, :, :]; S1 = np.roll(rim, -1, axis=0)[None, :, :]
SD = S1 - S0; SDl2 = np.einsum('inj,inj->in', SD, SD) + 1e-18

def seg_dists(blk):
    d = blk[:, None, :] - S0
    t = np.clip(np.einsum('mni,mni->mn', d, SD) / SDl2, 0, 1)
    proj = S0 + t[:, :, None] * SD
    return np.linalg.norm(proj - blk[:, None, :], axis=2).min(axis=1)

def near_rim(V):
    lo = rim.min(axis=0) - PAD; hi = rim.max(axis=0) + PAD
    sel = V[np.all((V >= lo) & (V <= hi), axis=1)]
    if len(sel) == 0: return np.empty((0, 3))
    keep = [seg_dists(sel[s:s+8000]) < PAD for s in range(0, len(sel), 8000)]
    return sel[np.concatenate(keep)]

def load_mesh(path, biggest=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    cand = [x for x in bpy.data.objects if x.type == 'MESH']
    o = max(cand, key=lambda x: len(x.data.vertices)) if biggest else cand[0]
    mw = o.matrix_world; me = o.data
    co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", co)
    V = co.reshape(-1, 3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)
    return o, me, mw, V

def rim_fold_med(o, me, mw):
    """rim区二面角中位数(稳健, 避max被退化面污染). 用全部rim点找邻接顶点."""
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(mw)
    bm.verts.ensure_lookup_table()
    kd = KDTree(len(bm.verts))
    for v in bm.verts: kd.insert(v.co, v.index)
    kd.balance()
    rim_idx = set()
    for p in rim:                          # 全部144点(不采样)
        co, idx, dist = kd.find(p)
        if dist is not None and dist < 0.010: rim_idx.add(idx)
    folds = []; seen = set()
    for vi in rim_idx:
        for e in bm.verts[vi].link_edges:
            if e.index in seen or len(e.link_faces) != 2: continue
            seen.add(e.index)
            n1 = e.link_faces[0].normal; n2 = e.link_faces[1].normal
            folds.append(np.degrees(np.arccos(np.clip(n1.dot(n2), -1, 1))))
    bm.free()
    folds = np.array(folds) if folds else np.array([0.0])
    return np.median(folds), len(folds), len(rim_idx)

def chamfer(src, kd):
    out = np.empty(len(src))
    for i, v in enumerate(src):
        r = kd.find(v); out[i] = r[2] if r and r[2] is not None else 9.9
    return out * 1000

# 高模 rim 区(两低模共用同一组高模点)
oh, meh, mwh, Vh = load_mesh(HI)
eh = near_rim(Vh)
kdh = KDTree(len(eh))
for i, v in enumerate(eh): kdh.insert(v, i)
kdh.balance()
fh_med, fh_e, fh_v = rim_fold_med(oh, meh, mwh)
print(f"高模: rim区点={len(eh):,} rim折角中位={fh_med:.1f}° (顶点{fh_v}/边{fh_e})\n")

for name, path in LOs.items():
    if not os.path.exists(path):
        print(f"[{name}] ✗ 文件不存在: {path}"); continue
    ol, mel, mwl, Vl = load_mesh(path, biggest=False)
    el = near_rim(Vl)
    kdl = KDTree(len(Vl))
    for i, v in enumerate(Vl): kdl.insert(v, i)
    kdl.balance()
    h2l = chamfer(eh, kdl); l2h = chamfer(el, kdh)
    fl_med, fl_e, fl_v = rim_fold_med(ol, mel, mwl)
    nq = sum(1 for p in mel.polygons if len(p.vertices) == 4)
    print(f"[{name}] 面={len(mel.polygons):,} quad={nq/len(mel.polygons)*100:.1f}% rim区点={len(el):,} rim折角中位={fl_med:.1f}°")
    print(f"    高模→低模: 中位={np.median(h2l):.3f} p95={np.percentile(h2l,95):.3f} max={h2l.max():.3f}mm")
    print(f"    低模→高模: 中位={np.median(l2h):.3f} p95={np.percentile(l2h,95):.3f} max={l2h.max():.3f}mm")
print("CMP_DONE")
