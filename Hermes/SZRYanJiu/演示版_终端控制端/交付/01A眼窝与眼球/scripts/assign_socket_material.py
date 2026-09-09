# -*- coding: utf-8 -*-
"""给眼窝碗面赋独立材质 'EyeSocket', 供 QR 的 UseMaterialIds 沿 rim 布线.

原理: make_eye_socket 已删净 rim 内皮肤面, make_eye_cup 在 rim 内重建碗面
→ "面中心XZ投影落在 rim 轮廓(manual json)内" 的面 = 纯眼窝碗面.
碗面赋新材质, 皮肤保持原材质 → 材质边界(碗/皮肤公共边)正好=rim
→ QR 的 UseMaterialIds 沿材质边界布线 = 沿眼睑缘布线, 保住眼窝结构.

**输出独立文件**(不覆盖 01_1_eye_socket.blend): 该文件同时是04烘焙的高模源,
  烘焙脚本会遍历所有材质的贴图节点; 若在原文件上加红色材质, 眼窝区烘焙出来会变红.
  所以: 02_qr_auto 读 _qr 版, 04_bake 仍读原版(材质/贴图完全不变).
  不侵入 socket_ops(用户验证过的权威眼窝流程), 独立后处理."""
import bpy, os, json
import numpy as np
import bmesh

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
HI = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket_qr.blend")
MAN = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(MAN, encoding="utf-8"))

def rim_xz(side):
    return np.array([(p[0], p[2]) for p in cont[side]["rim_3d"] if p is not None], dtype=np.float64)
PL, PR = rim_xz("L"), rim_xz("R")

# rim 3D 折线(用于深度判据)
def rim_p3d(side):
    return np.array([p for p in cont[side]["rim_3d"] if p is not None], dtype=np.float64)  # (N,3)
RL, RR = rim_p3d("L"), rim_p3d("R")

def rim_diag(P):
    """该眼 rim 的 bbox 对角线 = 自适应尺度(碗内面到rim折线距离不会超过它)."""
    return float(np.linalg.norm(P.max(axis=0) - P.min(axis=0)))
DIAGL, DIAGR = rim_diag(RL), rim_diag(RR)

def rim_plane(P):
    """该眼 rim 拟合平面 → (中心, 单位法线指向脸前方).
    眼窝碗从rim环往**深处**凹(depth>0), 眼睑/眉部皮肤在rim环**前方**(depth<0)."""
    ctr = P.mean(axis=0)
    u, s, vt = np.linalg.svd(P - ctr)
    n = vt[2]                          # 最小奇异向量 = 平面法线
    if n[1] > 0: n = -n                # 统一指向脸前方(-y)
    return ctr, n, float(s[2])

def plane_depth(Pts, ctr, n):
    """点到rim平面的有符号深度: >0 = 碗内侧(眼球方向), <0 = 外侧(眼皮/额头皮肤)."""
    return (Pts - ctr) @ (-n)

PLN_L = rim_plane(RL); PLN_R = rim_plane(RR)
# 容差: rim bbox对角线的0.15%(≈0.06mm) — 只吸收平面拟合噪声.
# 实测分界零重叠: 真碗面depth全≥+0.01mm, 溢出面全≤-0.01mm, 分界就在rim平面上.
# ⚠曾误设0.8%(=0.3mm): 上睑缘溢出面(depth -0.3~-0.01mm)会漏网 — 那正是用户肉眼可见的红色溢出.
TOL = max(DIAGL, DIAGR) * 0.0015

def seg_dist_batch(Pts, P):
    """Pts(M,3) 各点到闭合折线 P(N,3) 的最近3D距离 → (M,).
    ⚠关键: 必须用3D距离, 不能只用XZ投影 — 后脑勺面(y≈+90mm)的XZ投影
      会落进眼裂XZ范围被误判成碗面(曾导致136/350=38.9%假面, QR被假边界扰乱布线)."""
    S0 = P[None, :, :]; S1 = np.roll(P, -1, axis=0)[None, :, :]      # (1,N,3)
    SD = S1 - S0; SDl2 = np.einsum('inj,inj->in', SD, SD) + 1e-18    # (1,N)
    diff = Pts[:, None, :] - S0                                      # (M,N,3)
    t = np.clip(np.einsum('inj,inj->in', diff, SD) / SDl2, 0, 1)     # (M,N)
    proj = S0 + t[:, :, None] * SD                                   # (M,N,3)
    return np.linalg.norm(proj - Pts[:, None, :], axis=2).min(axis=1)  # (M,)

def pip_batch(pts, poly):
    """射线法 point-in-polygon, 向量化. pts(N,2) poly(M,2)."""
    x, z = pts[:, 0], pts[:, 1]
    n = len(poly); inside = np.zeros(len(pts), bool)
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]; xj, zj = poly[j]
        dz = zj - zi
        cond = ((zi > z) != (zj > z))
        xint = np.where(np.abs(dz) > 1e-12, (xj - xi) * (z - zi) / np.where(dz == 0, 1e-12, dz) + xi, 1e18)
        inside ^= cond & (x < xint)
        j = i
    return inside

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=HI)
obj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
me = obj.data; mw = obj.matrix_world
print(f"高模: {obj.name} 面={len(me.polygons):,} 原材质槽={len(me.materials)}")

# 面中心世界坐标
C = np.empty((len(me.polygons), 3), dtype=np.float64)
for i, p in enumerate(me.polygons):
    w = mw @ p.center
    C[i] = (w.x, w.y, w.z)

# bbox 粗筛(含Y深度, 先滤掉后脑勺) → pip 精判 → 3D深度判据(决定性)
allr = np.vstack([PL, PR]); pad = 0.003
# Y 深度范围取 rim 的 Y ± 自适应余量(rim bbox 对角线), 排除 y≈+90mm 的后脑勺面
rimy = np.array([q[1] for s in ("L", "R") for q in cont[s]["rim_3d"] if q is not None])
ypad = max(DIAGL, DIAGR) * 0.5
m = ((C[:,0] >= allr[:,0].min()-pad) & (C[:,0] <= allr[:,0].max()+pad) &
     (C[:,2] >= allr[:,1].min()-pad) & (C[:,2] <= allr[:,1].max()+pad) &
     (C[:,1] >= rimy.min()-ypad) & (C[:,1] <= rimy.max()+ypad))
cand = np.where(m)[0]
print(f"bbox候选(含Y深度滤)={len(cand):,}")

# 分眼判定: XZ pip(在眼睑缘轮廓内) + 3D距rim折线在尺度内 + **rim平面内侧**(碗方向)
# ⚠第三个条件是必需的: 上眼睑/眉部皮肤的XZ投影也落在rim轮廓内(实测413面全部"在rim内"),
#   且距rim仅1.71mm(远小于对角线阈值), 但在rim平面**前方**(depth -5.31~-0.01mm) →
#   只靠pip+距离会把它们当碗面 = 用户肉眼可见的红色材质溢出.
#   实测真碗面depth全≥+0.01mm、溢出面全≤-0.01mm, 分界干净无重叠.
sockL, sockR = [], []
rejL, rejR = [], []          # 被平面判据拒掉的(溢出)面, 供统计
for idx in cand:
    xz = C[idx][[0, 2]]
    okL = pip_batch(xz[None], PL)[0]; okR = pip_batch(xz[None], PR)[0]
    if not (okL or okR):
        continue
    # 3D 距离判据: 到所属眼 rim 折线的最近距离必须在该眼 rim 尺度内
    dL = seg_dist_batch(C[idx][None], RL)[0]
    dR = seg_dist_batch(C[idx][None], RR)[0]
    # 平面深度判据: 必须在rim平面内侧(碗方向), 容差吸收平面拟合噪声
    depL = plane_depth(C[idx][None], PLN_L[0], PLN_L[1])[0]
    depR = plane_depth(C[idx][None], PLN_R[0], PLN_R[1])[0]
    side = None
    if okL and dL < DIAGL: side = 'L'
    elif okR and dR < DIAGR: side = 'R'
    elif dL < DIAGL: side = 'L'
    elif dR < DIAGR: side = 'R'
    if side is None: continue
    dep = depL if side == 'L' else depR
    if dep >= -TOL:
        (sockL if side == 'L' else sockR).append(idx)
    else:
        (rejL if side == 'L' else rejR).append(dep)
sock = np.array(sockL + sockR, dtype=np.int64)
print(f"rim内碗面={len(sock):,} (L={len(sockL)} R={len(sockR)})")
print(f"  平面判据拒掉(溢出)={len(rejL)+len(rejR):,} (L={len(rejL)} R={len(rejR)})")
if rejL or rejR:
    allr_d = np.array(rejL + rejR) * 1000
    print(f"    溢出面depth: min={allr_d.min():.3f} 中位={np.median(allr_d):.3f} max={allr_d.max():.3f}mm (全应<0)")
    for band, lo, hi in (("(-0.1,0]", -0.1, 0.0), ("(-1,-0.1]", -1.0, -0.1), ("≤-1mm", -99., -1.0)):
        n = int(((allr_d > lo) & (allr_d <= hi)).sum())
        if n: print(f"    {band}: {n}个")
print(f"  判据阈值: L眼rim对角线={DIAGL*1000:.1f}mm R眼={DIAGR*1000:.1f}mm 平面容差={TOL*1000:.3f}mm")
if len(sock) < 100:
    raise AssertionError(f"识别碗面过少({len(sock)}), rim轮廓或坐标可能不对!")

# 新材质 EyeSocket (皮肤=原槽, 碗=新槽)
mat = bpy.data.materials.get("EyeSocket") or bpy.data.materials.new("EyeSocket")
mat.use_nodes = True
bs = mat.node_tree.nodes.get("Principled BSDF")
if bs: bs.inputs['Base Color'].default_value = (0.80, 0.15, 0.15, 1.0)  # 红, 便于GUI辨认
names = [s.name if s else None for s in me.materials]
if "EyeSocket" not in names:
    me.materials.append(mat)
si = [s.name if s else None for s in me.materials].index("EyeSocket")
# 皮肤面归 0, 碗面归 si
mi = np.zeros(len(me.polygons), dtype=np.int32)
mi[sock] = si
me.polygons.foreach_set("material_index", mi)
me.update()
print(f"赋材质: 皮肤(idx0)={int((mi==0).sum()):,}  眼窝(idx{si})={int((mi==si).sum()):,}")

# 材质边界边统计(应贴 rim)
rimsegs = []
for P in (PL, PR):
    for i in range(len(P)):
        rimsegs.append((P[i], P[(i+1) % len(P)]))
S0 = np.array([s[0] for s in rimsegs]); S1 = np.array([s[1] for s in rimsegs])
SD = S1 - S0; SDl2 = np.einsum('ij,ij->i', SD, SD) + 1e-18
bm = bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table()
bound = 0; rim_d = []
for e in bm.edges:
    if len(e.link_faces) == 2:
        if e.link_faces[0].material_index != e.link_faces[1].material_index:
            bound += 1
            c = np.array(mw @ ((e.verts[0].co + e.verts[1].co) / 2))[[0, 2]]
            t = np.clip(np.einsum('ij,ij->i', c - S0, SD) / SDl2, 0, 1)
            proj = S0 + t[:, None] * SD
            rim_d.append(np.linalg.norm(proj - c[None, :], axis=1).min())
bm.free()
rim_d = np.array(rim_d) if rim_d else np.array([9.9])
print(f"材质边界边={bound}  距rim: 中位={np.median(rim_d)*1000:.3f}mm max={rim_d.max()*1000:.3f}mm")
if np.median(rim_d) > 0.002:
    print(f"  ⚠ 边界边偏离rim(中位{np.median(rim_d)*1000:.2f}mm>2mm), 识别可能不准")

# 保存到独立文件(原 01_1_eye_socket.blend 不动, 04烘焙继续读它)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"已保存: {OUT}")
print(f"  (原文件未改: {os.path.basename(HI)} — 04烘焙仍读它, 不会出现红色眼窝)")
print("SOCKET_MAT_DONE")
