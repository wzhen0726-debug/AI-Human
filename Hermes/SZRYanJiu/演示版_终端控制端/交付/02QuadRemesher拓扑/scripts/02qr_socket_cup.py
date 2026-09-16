# -*- coding: utf-8 -*-
"""02 QR 之后: 低模碗状眼窝重建(眼球坐进去).
2026-09-16 用户确认方向: "在低模上重建碗状眼窝(有碗面, 眼球坐进去)".

做法(全部随动, 无硬编码):
  ① 从 01_2 的真实眼球对象推导: 球心 yc(xz 与眼中心一致)、半径 R、间隙 clr(默认 0.0015m)
  ② 每个眼孔边界环(QR 输出的开放边界闭环) → 内收 N 圈; 第 k 圈半径 = 原半径×s_k,
     深度按【眼球同心球面+间隙】取值: y = yc + sqrt(max(0,(R+clr)^2 - r'^2))
     → 碗面天然包住眼球, 不穿球
  ③ 最内圈用小 n-gon 封底(旧版验证过: 单极点三角扇有放射条纹, 单 n-gon 盖干净)
  ④ smooth shading; 保存为新文件(不覆盖 02_qr_150k.blend)

输出: 02QR拓扑/输出/02_qr_150k_socket.blend
"""
import bpy, os, json, math, numpy as np, bmesh
import functools
print = functools.partial(print, flush=True)   # 日志实时可见(定位卡点)
from mathutils import Vector

D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
QR_BLEND = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k.blend")
EYE_BLEND = os.path.join(D, "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")
OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
J = json.load(open(os.path.join(D, "交付", "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))

# ---- ① 从 01_2 拿真实眼球的球心/半径 ----
bpy.ops.wm.open_mainfile(filepath=EYE_BLEND)
balls = [o for o in bpy.data.objects if o.type == 'MESH']
head = max(balls, key=lambda o: len(o.data.vertices))
eyeballs = [o for o in balls if o is not head]
BALL = {}
if eyeballs:
    for o in eyeballs:
        mw = np.array(o.matrix_world)
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        # v6(2026-09-16): 不能用顶点均值当球心 —— 角膜侧顶点更密, 均值被带偏,
        #   半径谱因此虚胖成 6.9~18.7mm(v5 用 max 的坑就源于此)。
        #   规范球体估计: 球心=包围盒中心; 半径=到该中心距离的 p90(含角膜凸起)。
        ctr = (co.min(axis=0) + co.max(axis=0)) * 0.5
        rr = np.linalg.norm(co - ctr, axis=1)
        rad = float(np.percentile(rr, 90))
        s = "L" if ctr[0] < 0 else "R"
        BALL[s] = (Vector(tuple(ctr)), rad)
        print(f"眼球[{s}]: 球心(bbox中心)({ctr[0]*1000:.1f},{ctr[1]*1000:.1f},{ctr[2]*1000:.1f})mm "
              f"半径(p90)={rad*1000:.2f}mm 半径谱[{rr.min()*1000:.1f}~{rr.max()*1000:.1f}]")
CLR = 0.0015   # 碗面与球面的间隙(眼球后极不穿碗底)

# ---- ①b 参考碗: 高模旧版眼窝(_eye_cup_ref.blend) 的深度剖面 ----
# 用户要求"类似之前高模上做的眼窝形状" → 逐点采样旧碗面的 y 作为低模碗的深度
REF_BLEND = os.path.join(D, "_eye_cup_ref.blend")
REF_BVH = {}
REF_TAG = {}
if os.path.exists(REF_BLEND):
    from mathutils.bvhtree import BVHTree
    bpy.ops.wm.open_mainfile(filepath=REF_BLEND)
    robj = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    rme = robj.data
    rvl = [tuple(v.co) for v in rme.vertices]
    for s in ("L", "R"):
        attr = rme.attributes.get("v44tag_" + s)
        if attr is None:
            continue
        tg = np.zeros(len(rme.polygons), dtype=np.int32)
        attr.data.foreach_get("value", tg)
        idxs = np.where(tg == 2)[0]           # 2 = 旧版碗面
        if len(idxs) < 50:
            continue
        pl = [list(rme.polygons[int(i)].vertices) for i in idxs]
        REF_BVH[s] = BVHTree.FromPolygons(rvl, pl)
        print(f"参考碗[{s}]: {len(pl)} 面 BVH 就绪")
else:
    print(f"⚠ 参考件不存在({os.path.basename(REF_BLEND)}), 将用眼球同心球剖面")

# ---- ② 打开 QR 低模, 对每个眼孔建碗 ----
bpy.ops.wm.open_mainfile(filepath=QR_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data
bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
# 碗面 tag 层(供自检/下游识别: 1=QR后新建的碗面)
_tag = bm.faces.layers.int.new("qrbowl")

# 内收圈比例(从边界往内, 8 圈 = 对齐旧版高模碗的 8 圈过渡): 单圈跨度小 → 剖面圆顺, 不成'一条槽'
# (旧版 make_eye_cup 验证: 单极点三角扇有放射条纹, n-gon 盖干净; 碗底被眼球挡住, 平整度不重要)
# (SCALES 由 _SCALES 取代, 见下)

for side in ("L", "R"):
    c3 = Vector(tuple(float(x) for x in J[side]['center']))
    if side not in BALL:
        print(f"[{side}] 01_2 里没找到眼球, 跳过")
        continue
    _bc = BALL[side][0]
    yc, R = _bc[1], BALL[side][1]
    bx, bz = _bc[0], _bc[2]     # ★以【眼球中心】为碗的轴心(轮廓中心与球心差~1.4mm, 直接用会吃掉间隙)
    # 找该眼孔的开放边界环
    oe = [e for e in bm.edges if len(e.link_faces) == 1 and (e.verts[0].co - c3).xz.length < 0.05]
    dg = {}
    for e in oe:
        a, b = e.verts
        dg.setdefault(a.index, []).append(b.index)
        dg.setdefault(b.index, []).append(a.index)
    st = [k for k in dg if len(dg[k]) == 2]
    if len(st) < 20:
        print(f"[{side}] 未找到孔环(边界边{len(oe)}), 跳过")
        continue
    ring0 = [st[0]]; pv, cu = -1, st[0]
    while True:
        cand = [q for q in dg[cu] if q != pv]
        if not cand or cand[0] == ring0[0]:
            break
        ring0.append(cand[0]); pv, cu = cu, cand[0]
    M = len(ring0)
    print(f"[{side}] 孔环 {M} 点 → 建碗(球心y{yc*1000:.1f} 半径{R*1000:.2f} 间隙{CLR*1000:.1f}mm)")
    ring_v = [bm.verts[i] for i in ring0]
    # ---- 绕序种子: 环上第一条与头模面共享的边; 头模面沿 a→b 则新面须沿 b→a(流形一致) ----
    bm.verts.index_update(); bm.edges.index_update(); bm.faces.index_update()
    _reverse_order = False
    _seed_found = False
    _newf_idx = set()
    for i in range(len(ring_v)):
        if _seed_found:
            break
        a = ring_v[i]; b = ring_v[(i + 1) % len(ring_v)]
        e = bm.edges.get((a, b))
        if e is None or len(e.link_faces) < 1:   # 孔环边此刻=边界边(仅头模1面), 不能要求>=2
            continue
        g = e.link_faces[0]
        # g 是否沿 a→b: 看 g 的 loop 起点
        _g_dir = None
        for l in g.loops:
            if l.edge.index == e.index:
                _g_dir = (l.vert.index == a.index)
                break
        if _g_dir is None:
            continue
        # 头模面沿 a→b(=True) → 新面须沿 b→a → 反转顺序
        _reverse_order = bool(_g_dir)
        _seed_found = True
    print(f"[{side}] 绕序种子: {'反转' if _reverse_order else '常规'} (与头模面共享边一致)")
    # 各点极坐标(相对眼中心 XZ)
    polar = []
    for v in ring_v:
        dx, dz = v.co.x - bx, v.co.z - bz
        polar.append((math.hypot(dx, dz), math.atan2(dz, dx)))
    CAP_N = M            # 最内圈点数
    # 等宽度偏移: 每圈沿径向内缩固定量 d_k = (k/n)*r_min (r_min=边界最小极径, 随动)
    # 修复用户报'一条特别长的薄环': 等比缩放在长轴方向环带过宽、短轴方向成薄片。
    _r_min = max(1e-4, min(r for (r, th) in polar))
    # v8(用户: "眼窝内的都是环线, 随rim环逐渐变小…最后成为一个点"):
    #   等比缩小保持 rim 形状轮廓逐圈变小 → 末环 0.15 → 极点收口(不再用 n-gon 平盖 '花生仁')
    _SCALES = [0.90, 0.80, 0.70, 0.59, 0.48, 0.37, 0.26, 0.15]
    _NB = len(_SCALES)
    last_ring = ring_v
    made = 0
    _new_faces = []
    # ---- v10: 每条射线预计算【表面路径的累计弧长】→ 各圈按其等分点放置 ----
    def _surf_point(r_i, th_i, s_f):
        """在射线 i 上取比例 s_f (1=边界,0=中心) 的位置(含深度)"""
        r2 = max(r_i * s_f, 0.0005)
        x2 = bx + r2 * math.cos(th_i)
        z2 = bz + r2 * math.sin(th_i)
        y2 = None
        if side in REF_BVH:
            _hit = REF_BVH[side].ray_cast(Vector((x2, c3.y - 0.060, z2)), Vector((0.0, 1.0, 0.0)))
            if _hit and _hit[0] is not None:
                y2 = float(_hit[0][1])
        if y2 is None:
            y2 = yc + math.sqrt(max(0.0, (R + CLR) ** 2 - r2 * r2))
        return Vector((x2, y2, z2))

    _NS = 64                     # 采样步数
    _sgrid = [1.0 - k / _NS for k in range(_NS + 1)]     # 1.0 → 0.0
    _paths = []                  # 每条射线的采样点
    _cum = []                    # 每条射线的累计弧长
    for _i, (r_i, th_i) in enumerate(polar):
        pts = [_surf_point(r_i, th_i, sf) for sf in _sgrid]
        cum = [0.0]
        for _k in range(1, len(pts)):
            cum.append(cum[-1] + (pts[_k] - pts[_k - 1]).length)
        _paths.append(pts)
        _cum.append(cum)

    def _pt_at_frac(i, frac):
        """射线 i 上累计弧长占比 frac 处的点(线性插值)"""
        cum = _cum[i]
        tgt = frac * cum[-1]
        lo = 0
        for _k in range(len(cum)):
            if cum[_k] >= tgt:
                lo = _k - 1 if _k > 0 else 0
                break
        else:
            lo = len(cum) - 2
        c0, c1 = cum[lo], cum[lo + 1]
        w = 0.0 if c1 <= c0 else (tgt - c0) / (c1 - c0)
        return _paths[i][lo].lerp(_paths[i][lo + 1], w)

    _SCALES_V11 = [0.90, 0.80, 0.70, 0.59, 0.48, 0.37, 0.26, 0.15]
    for si in range(1, _NB + 1):
        new_ring = []
        frac = si / (_NB + 1)        # 弧长等分比例(留出到极点的最后一段)
        s_prop = _SCALES_V11[min(si, len(_SCALES_V11)) - 1]   # 等比缩小对照
        w_deep = (si / _NB) ** 2     # 0..1: 越深越回到'等比缩小'(防深层星状折叠)
        for _i in range(len(polar)):
            pa = _pt_at_frac(_i, frac)                      # 弧长等分点
            r_i, th_i = polar[_i]
            rp = max(r_i * s_prop, 0.0005)
            xp = bx + rp * math.cos(th_i)
            zp = bz + rp * math.sin(th_i)
            yp = None
            if side in REF_BVH:
                _hit = REF_BVH[side].ray_cast(Vector((xp, c3.y - 0.060, zp)), Vector((0.0, 1.0, 0.0)))
                if _hit and _hit[0] is not None:
                    yp = float(_hit[0][1])
            if yp is None:
                yp = yc + math.sqrt(max(0.0, (R + CLR) ** 2 - rp * rp))
            pp = Vector((xp, yp, zp))
            v2 = bm.verts.new(pa.lerp(pp, w_deep))
            new_ring.append(v2)
        bm.verts.ensure_lookup_table()
        for i in range(len(last_ring)):
            a = last_ring[i]; b = last_ring[(i + 1) % len(last_ring)]
            c = new_ring[(i + 1) % len(new_ring)]; dv = new_ring[i]
            if _reverse_order:
                quad = (b, a, dv, c)          # 种子约定: 与头模面共享边走相反方向
            else:
                quad = (a, b, c, dv)
            try:
                _nf = bm.faces.new(quad); _nf[_tag] = 1; _new_faces.append(_nf); made += 1
            except Exception:
                try:
                    _nf = bm.faces.new(tuple(reversed(quad))); _nf[_tag] = 1; _new_faces.append(_nf); made += 1
                except Exception:
                    pass
        last_ring = new_ring
    # ---- ③ 最内圈用单 n-gon 封底 ----
    # ---- 极点收口(用户: "最后成为一个点"): 单顶点 + 三角扇 ----
    try:
        _px = float(np.mean([v.co.x for v in last_ring]))
        _pz = float(np.mean([v.co.z for v in last_ring]))
        _py = None
        if side in REF_BVH:
            _hit = REF_BVH[side].ray_cast(Vector((_px, c3.y - 0.060, _pz)), Vector((0.0, 1.0, 0.0)))
            if _hit and _hit[0] is not None:
                _py = float(_hit[0][1])
        if _py is None:
            _py = yc + (R + CLR)
        _pole = bm.verts.new(Vector((_px, _py, _pz)))
        bm.verts.ensure_lookup_table()
        _nf = 0
        for i in range(len(last_ring)):
            a = last_ring[i]; b = last_ring[(i + 1) % len(last_ring)]
            tri = (a, b, _pole) if not _reverse_order else (b, a, _pole)
            try:
                _f3 = bm.faces.new(tri); _f3[_tag] = 1; made += 1; _nf += 1
            except Exception:
                pass
        print(f"[{side}] 极点收口: 极点({_px*1000:.1f},{_py*1000:.1f},{_pz*1000:.1f}) 扇形三角 {_nf} 个")
    except Exception as _e:
        print(f"[{side}] 极点收口失败: {_e}")
    bm.normal_update()
    print(f"[{side}] 新建面 {made} (种子绕序{'反转' if _reverse_order else '常规'})")

# ---- 收尾: 关掉碗与孔环交界处残余的开放边(建面时个别quad异常被跳过) ----
# ❌禁止全局 recalc_face_normals: 按连通岛整体重定向 → 会把腿等区域翻掉(实测245面翻转, 用户截图报过)
_oe_left = [e for e in bm.edges if len(e.link_faces) == 1]
if _oe_left:
    try:
        bmesh.ops.holes_fill(bm, edges=_oe_left, sides=8)
        _after = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        print(f"收尾封口: 开放边 {len(_oe_left)} → {_after}")
    except Exception as _e:
        print(f"收尾封口失败: {_e}")
bm.normal_update()
# 碗面 tag 已在建面时逐个打上(引用失效教训: 事后用 BMFace 列表会失效)
bm.to_mesh(me); bm.free()
me.update()
for p in me.polygons:
    p.use_smooth = True
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)
