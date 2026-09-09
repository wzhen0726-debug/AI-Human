# -*- coding: utf-8 -*-
"""决定性判据: rim折线(眼睑缘)到低模最近"边"的距离 — 衡量QR有没有沿rim布出边环.
对 rim 上密集采样点, 求到低模所有边的最近3D距离. 越小=rim处真有边跟着走.
并排对比 新版 vs A备份(同判据)."""
import bpy, os, json
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
LOs = {
    "新(材质分区修复)": os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k.blend"),
    "A备份(角度硬边)":   os.path.join(D, "交付", "02QuadRemesher拓扑", "_backup_20260908_A配置", "02_qr_150k.blend"),
}
cont = json.load(open(os.path.join(D, "交付", "01A眼窝与眼球", "screenshots", "3ddfa",
                                   "eyelid_contour_manual.json"), encoding="utf-8"))
rim = np.vstack([np.array(cont[s]["rim_3d"]) for s in ("L", "R")])
# rim 上按弧长密集采样(每2mm一个), 避免只用144个原始点
def densify(P, step=0.002):
    out = []
    for i in range(len(P)):
        a, b = P[i], P[(i+1) % len(P)]
        L = np.linalg.norm(b-a); n = max(1, int(L/step))
        for k in range(n): out.append(a + (b-a)*k/n)
    return np.array(out)
RL = densify(np.array(cont["L"]["rim_3d"])); RR = densify(np.array(cont["R"]["rim_3d"]))
Q = np.vstack([RL, RR])
print(f"rim密集采样点={len(Q)} (L={len(RL)} R={len(RR)})")

for name, path in LOs.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    o = [x for x in bpy.data.objects if x.type == 'MESH'][0]
    mw = o.matrix_world; me = o.data
    co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", co)
    V = co.reshape(-1, 3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)
    ev = np.empty(len(me.edges)*2, dtype=np.int32); me.edges.foreach_get("vertices", ev)
    E = ev.reshape(-1, 2)
    A = V[E[:, 0]]; Bv = V[E[:, 1]]
    SD = Bv - A; SDl2 = np.einsum('ij,ij->i', SD, SD) + 1e-18
    # 分块: 每个rim采样点到所有边的最近距离
    dmin = np.empty(len(Q))
    CH = 60
    for s in range(0, len(Q), CH):
        blk = Q[s:s+CH]                       # (m,3)
        d = blk[:, None, :] - A[None, :, :]   # (m,E,3)
        t = np.clip(np.einsum('mei,ei->me', d, SD) / SDl2[None, :], 0, 1)
        proj = A[None, :, :] + t[:, :, None] * SD[None, :, :]
        dmin[s:s+CH] = np.linalg.norm(proj - blk[:, None, :], axis=2).min(axis=1)
    d = dmin * 1000
    # 分眼
    dL = d[:len(RL)] * 1000; dR = d[len(RL):] * 1000
    print(f"\n[{name}] rim→低模最近边距离:")
    print(f"    整体: 中位={np.median(d):.2f} p90={np.percentile(d,90):.2f} max={d.max():.2f}mm")
    print(f"    L眼: 中位={np.median(dL):.2f} max={dL.max():.2f}mm   R眼: 中位={np.median(dR):.2f} max={dR.max():.2f}mm")
    print(f"    <1mm: {int((d<1).sum())}/{len(d)} ({(d<1).mean()*100:.0f}%)  <2mm: {int((d<2).sum())} ({(d<2).mean()*100:.0f}%)")
print("EDGE_DONE")
