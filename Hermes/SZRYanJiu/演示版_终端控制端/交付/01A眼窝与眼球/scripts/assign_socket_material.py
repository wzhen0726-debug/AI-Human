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

# ---- v58 重复面补红(2026-09-11, 判据定案): ----
# 根因(_diag_rlow实测): 用户所见灰楔 = 原始扫描的重叠重复面, 与碗面共面/近共面但无tag.
#   R下睑中央灰面距原始tag碗面0.03-0.48mm(face1209172等25+个), 正面看盖住红碗面 → 灰楔.
# ❌v56距离+前方判定: 共面时(C-near_w)≈零向量, 前方符号=数值噪声, 随机漏一半(补163仍见118).
# ❌v57射线可见性: 共面的红/灰面射线随机命中其一, 命中红→跳过, 同位置灰面照样可见.
# ❌迭代(BVH对已补红面重建): 网格密(边长~0.4mm)沿表面形成0.5mm链, 6轮650个仍增长=爬藤外扩.
# ❌阈值放宽(1.0/1.5mm单pass): 前方灰面距离连续分布0.002→29mm无断层, 放宽必把真眼睑皮肤染红
#   (vision实测1.5mm版"红区偏大/红尖角伸入灰区").
# ✅v58: 单pass, 距离只对【原始tag碗面】量, 阈值0.5mm — 只抓共面重复堆栈(R下睑灰楔全≤0.48mm),
#   真皮肤距碗面>1mm(前方灰面p50=9.3mm)不误收; 不测前后方向(共面时数值不稳, 且堆栈在碗后也无害);
#   采样面心+全顶点, 任一点距原始碗面<0.5mm即补红. 确定/有界/一遍收敛/零拓扑改动.
from mathutils.bvhtree import BVHTree as _BVHTree
import json as _json58
_cont_p = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
_mw = np.array(obj.matrix_world); _inv_mw = np.linalg.inv(_mw)
_co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", _co)
_VL = _co.reshape(-1,3)
_VW = _VL@_mw[:3,:3].T + _mw[:3,3]
_bmask = (mi == si)          # 此刻mi只有tag碗面 = 原始碗面真值
_bowl_polys = [list(me.polygons[fi].vertices) for fi in np.where(_bmask)[0]]
_svc_b = _BVHTree.FromPolygons([tuple(v) for v in _VL], _bowl_polys)   # 只建一次, 永不重建
_C = np.array([_VW[list(me.polygons[i].vertices)].mean(axis=0) for i in range(n)])
_bb_lo = _C[_bmask].min(axis=0)-0.010; _bb_hi = _C[_bmask].max(axis=0)+0.010
_in_bb = ((_C[:,0]>=_bb_lo[0])&(_C[:,0]<=_bb_hi[0])&(_C[:,1]>=_bb_lo[1])&(_C[:,1]<=_bb_hi[1])
          &(_C[:,2]>=_bb_lo[2])&(_C[:,2]<=_bb_hi[2]))
_cand = np.where(_in_bb & ~_bmask)[0]
# v58b 收紧(2026-09-11 用户GUI截图: 红区外扩成锯齿大片爬到眼睑):
#   ❌原v58用[面心+全顶点任一]<0.5mm — 大皮肤三角只要一个顶点碰到碗面就整面染红,
#     补红370个中136个(36.8%)XZ超手描rim>2mm、65个y在睑前 = 染到眼睑皮肤上 → 红区锯齿外扩.
#     对比基线: tag碗面自身XZ超rim>2mm = 0% (碗面从不越rim), 说明那136个是误染.
#   ✅收紧两道闸: ①只用【面心】测距(不采顶点) — 面心贴碗才是真共面重复面, 大面搭边不算;
#     ②y闸门: 面心y不得比该侧rim最前y更靠前(容差0.5mm), 排除睑前重复面.
_cont=_json58.load(open(_cont_p,encoding="utf-8"))
_RLy=np.array([q[1] for q in _cont["L"]["rim_3d"] if q is not None])
_RRy=np.array([q[1] for q in _cont["R"]["rim_3d"] if q is not None])
_yminL=_RLy.min()-0.0005; _yminR=_RRy.min()-0.0005
# v58c XZ闸门(2026-09-11 用户GUI截图报红区边缘尖刺锯齿): v58b只加了y闸门, 漏加XZ rim闸门.
#   实测167个补红面里41个距rim>2mm(面心戳出rim环外缘), 整面染红 → 红色以尖刺状戳出边界.
#   tag碗面基线自身XZ超rim>2mm=0% → 补红面也不应超. 加: 面心距rim>2mm不补.
_RL3=np.array([q for q in _cont["L"]["rim_3d"] if q is not None])
_RR3=np.array([q for q in _cont["R"]["rim_3d"] if q is not None])
def _seg_d3(Pts,P):
    S0=P[None,:,:]; S1=np.roll(P,-1,axis=0)[None,:,:]; SD=S1-S0
    SDl2=np.einsum('inj,inj->in',SD,SD)+1e-18; d=Pts[:,None,:]-S0
    t=np.clip(np.einsum('mni,mni->mn',d,SD)/SDl2,0,1); proj=S0+t[:,:,None]*SD
    return np.linalg.norm(proj-Pts[:,None,:],axis=2).min(axis=1)
_fix = []
for _fi in _cand:
    _c = _C[_fi]
    if (_c[0] < 0 and _c[1] < _yminL) or (_c[0] > 0 and _c[1] < _yminR): continue   # 睑前面不补
    if min(_seg_d3(_c[None,:],_RL3)[0], _seg_d3(_c[None,:],_RR3)[0]) > 0.002: continue  # 距rim>2mm不补
    _pl = _c@_inv_mw[:3,:3].T + _inv_mw[:3,3]
    _h = _svc_b.find_nearest(_pl)
    if _h[0] is not None and abs(_h[3]) < 0.0005:      # 面心贴原始碗面<0.5mm = 共面重复面
        _fix.append(int(_fi))
if _fix:
    mi[np.array(_fix)] = si
    me.polygons.foreach_set("material_index", mi); me.update()
print(f"v58c重复面补红: 候选{len(_cand)} 补红={len(_fix)} (面心贴碗<0.5mm + y在rim后 + 距rim≤2mm, 单pass有界)")

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
