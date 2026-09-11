# -*- coding: utf-8 -*-
"""给眼窝碗面赋独立材质 'EyeSocket', 供 QR 的 UseMaterialIds 沿 rim 布线.

原理(2026-09-09 重写): make_eye_cup 在 rim 边界环上重建碗面时, 已给每个新建碗面
打上 bmesh per-face int 层标记 v44tag_L / v44tag_R == 2 (socket_ops.py:522/532).
这批面从 rim 环长出来, 材质边界天然就是 rim —— 是最权威的碗面身份标识.

⚠历史弯路: 旧版不用tag, 改用"面心XZ投影pip+SVD拟合rim平面深度+3D距离"事后重新猜
  哪些是碗面. 但手描rim轮廓(eyelid_contour_manual.json)≠make_eye_cup实际找到的
  开放边界环ring0, 两者位置有偏差 → 几何判据既漏判(碗口翻出rim的XZ包围)又误判
  (把真碗面当溢出). 直接用tag层, 零猜测, 边界100%贴rim.

**输出独立文件**(不覆盖 01_1_eye_socket.blend): 该文件同时是04烘焙的高模源,
  烘焙脚本会遍历所有材质的贴图节点; 若在原文件上加红色材质, 眼窝区烘焙出来会变红.
  所以: 02_qr_auto 读 _qr 版, 04_bake 仍读原版(材质/贴图完全不变).
  不侵入 socket_ops(用户验证过的权威眼窝流程), 独立后处理."""
import bpy, os
import numpy as np

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
HI = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket_qr.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=HI)
obj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
me = obj.data
print(f"高模: {obj.name} 面={len(me.polygons):,} 原材质槽={len(me.materials)}")

# ---- 读 make_eye_cup 的拓扑标记: v44tag_L/R == 2 = 碗面(边界=rim) ----
attrL = me.attributes.get("v44tag_L")
attrR = me.attributes.get("v44tag_R")
if attrL is None and attrR is None:
    raise RuntimeError("v44tag_L/R 层不存在! make_eye_cup 未打标记或层未持久化. "
                       "请确认 01_1_eye_socket.blend 是 make_eye_cup 的直接产物.")
n = len(me.polygons)
tagL = np.zeros(n, dtype=np.int32); tagR = np.zeros(n, dtype=np.int32)
if attrL is not None: attrL.data.foreach_get("value", tagL)
if attrR is not None: attrR.data.foreach_get("value", tagR)
sock = np.where((tagL == 2) | (tagR == 2))[0]
nL = int((tagL == 2).sum()); nR = int((tagR == 2).sum())
print(f"tag碗面: L={nL:,} R={nR:,} 合={len(sock):,}  (边界=make_eye_cup的rim环, 天然贴合)")
if len(sock) < 100:
    raise AssertionError(f"tag碗面过少({len(sock)}), v44tag层可能损坏!")

# ---- 新材质 EyeSocket (皮肤=原槽, 碗=新槽) ----
mat = bpy.data.materials.get("EyeSocket") or bpy.data.materials.new("EyeSocket")
mat.use_nodes = True
bs = mat.node_tree.nodes.get("Principled BSDF")
if bs: bs.inputs['Base Color'].default_value = (0.80, 0.15, 0.15, 1.0)  # 红, 便于GUI辨认
names = [s.name if s else None for s in me.materials]
if "EyeSocket" not in names:
    me.materials.append(mat)
si = [s.name if s else None for s in me.materials].index("EyeSocket")
# 皮肤面归 0, 碗面归 si
mi = np.zeros(n, dtype=np.int32)
mi[sock] = si
me.polygons.foreach_set("material_index", mi)
me.update()
print(f"赋材质: 皮肤(idx0)={int((mi==0).sum()):,}  眼窝(idx{si})={int((mi==si).sum()):,}")

# ---- 材质边界统计: 碗/皮肤公共边应正好=rim环(碗面从rim长出, 边界必然贴rim) ----
import bmesh
bm = bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table()
bound = sum(1 for e in bm.edges if len(e.link_faces) == 2 and
            e.link_faces[0].material_index != e.link_faces[1].material_index)
# 碗面连通块数(每眼应1块)
from collections import defaultdict
from collections import deque
edge2face = defaultdict(list)
for fi in sock:
    vs = list(me.polygons[fi].vertices)
    for a in range(len(vs)):
        edge2face[tuple(sorted((vs[a], vs[(a+1) % len(vs)])))].append(int(fi))
adj = defaultdict(set); sockset = set(sock.tolist())
for e, fs in edge2face.items():
    rf = [f for f in fs if f in sockset]
    for a in range(len(rf)):
        for b in range(a+1, len(rf)):
            adj[rf[a]].add(rf[b]); adj[rf[b]].add(rf[a])
seen = set(); ncomp = 0
for f in sockset:
    if f in seen: continue
    ncomp += 1; q = deque([f]); seen.add(f)
    while q:
        x = q.popleft()
        for nb in adj[x]:
            if nb not in seen: seen.add(nb); q.append(nb)
bm.free()
print(f"材质边界边={bound}  碗面连通块={ncomp}(应=2, 左右各一)")
if ncomp != 2:
    print(f"  ⚠ 碗面连通块≠2({ncomp}), 可能有孤岛或断裂")

# ---- 保存到独立文件(原 01_1_eye_socket.blend 不动, 04烘焙继续读它) ----
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"已保存: {OUT}")
print(f"  (原文件未改: {os.path.basename(HI)} — 04烘焙仍读它, 不会出现红色眼窝)")
print("SOCKET_MAT_DONE")
