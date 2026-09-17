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
QR_BLEND = os.path.join(D, "02QR拓扑", "_中间", "02_qr_150k.blend")
EYE_BLEND = os.path.join(D, "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")
OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
J = json.load(open(os.path.join(D, "01a眼窝眼球", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))

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
    # 2026-09-17 v18 用户口径: rim→最深环【线性】缩放(参考碗实测每环缩放步进恒定)
    _S_DEEP = 0.152          # 最深环(眼窝心)半径比 = 参考碗实测 0.153
    _NB = 8
    _SCALES = [1.0 - (1.0 - _S_DEEP) * (k / _NB) for k in range(1, _NB + 1)]

    # ---- 2026-09-17 v18 用户口径(实测其参考碗反推 = 纯线性插值, 无任何非线性剖面) ----
    # 用户方法: rim环 → 缩放+Y轴打平成"眼窝心"环(最深环, 全平) → 中间均匀分段(Ctrl+R) → 再挤一点合并中心.
    # 参考碗逐环实测: 深度步进 +3.13mm×7 全等; 波动线性衰减 (8-k)/8×rim波动; 最深环 std=0(全平); 极点再深+2.17mm.
    # 实现 = y_k_i = (1-t_k)·rim_y_i + t_k·y_deep, t_k = k/8 → k=8 时恰好全平.
    # y_deep(眼窝心平面) = rim_y均值 + 0.662×eye_w (参考碗实测 24.6mm @ 37.13mm; 随尺寸随动)
    _rim_y = [v.co.y for v in ring_v]
    _eye_w = float(J[side].get('width_mm', 37.0)) / 1000.0
    _y_deep = float(np.mean(_rim_y)) + 0.675 * _eye_w  # 0.675 = 参考碗 deepest ring 绝对y对齐实测反推
    _POLE_STEP = 0.058 * _eye_w
    def _t_of(s_k):
        return (1.0 - s_k) / max(1e-9, (1.0 - _S_DEEP))
    def _y_of(s_k, _i):
        _t = _t_of(s_k)
        return (1.0 - _t) * _rim_y[_i] + _t * _y_deep

    # ---- v13(用户: 让蓝线尽量均分 1 和 2; 不许出现错位穿插) ----
    # 只调【第1圈内环】的径向标量 s1, 使 band1(rim→环1) 与 band2(环1→环2) 的表面宽度相等。
    # w1(s1): s1 变大 → 环1 外移 → w1 变小;  w2(s1): s1 变大 → 跨距变大 → w2 变大。
    # 故 w1-w2 对 s1 单调递减 → 二分; 且限定 s1 ∈ (s2, 0.995) 保证与环2不交叠。
    def _ring_at(s_k):
        out = []
        for _i, (r, th) in enumerate(polar):
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            # v18 用户口径: rim_y 线性插值到眼窝心平面
            y2 = _y_of(s_k, _i)
            out.append(Vector((x2, y2, z2)))
        return out

    def _bandw(a_pts, b_pts):
        return sum((a_pts[i] - b_pts[i]).length for i in range(len(a_pts))) / max(1, len(a_pts))

    try:
        _bpts = [v.co.copy() for v in ring_v]
        _s2 = _SCALES[1]
        _r2pts = _ring_at(_s2)

        def _diff(s1):
            _r1 = _ring_at(s1)
            return _bandw(_bpts, _r1) - _bandw(_r1, _r2pts)

        lo, hi = _s2 + 0.005, 0.995
        if _diff(lo) < 0:            # 全区间 w1<w2(罕见): |差值| 在 lo 最小 → 取 lo
            s1_star = lo
        elif _diff(hi) > 0:          # 即使贴到 rim 仍 w1>w2(深落差固有) → 取 hi"
            s1_star = hi
        else:
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                if _diff(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            s1_star = 0.5 * (lo + hi)
        _w1 = _bandw(_bpts, _ring_at(s1_star))
        _w2 = _bandw(_ring_at(s1_star), _r2pts)
        print(f"[{side}] v13 蓝线均分: s1 {_SCALES[0]:.3f} → {s1_star:.3f}  band1={_w1*1000:.2f}mm band2={_w2*1000:.2f}mm 比值={_w1/max(_w2,1e-9):.3f}", flush=True)
        _SCALES[0] = s1_star
    except Exception as _e:
        print(f"[{side}] v13 异常({_e}) → 用原 SCALES", flush=True)
    last_ring = ring_v
    made = 0
    _new_faces = []
    _rings_built = []      # v16: 记录新建各圈顶点, 便于按用户指定圈做局部Y位移
    for si, s_k in enumerate(_SCALES, start=1):
        new_ring = []
        for _i, (r, th) in enumerate(polar):
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            # v18 用户口径: rim_y 线性插值到眼窝心平面(末环全平)
            y2 = _y_of(s_k, _i)
            v2 = bm.verts.new(Vector((x2, y2, z2)))
            new_ring.append(v2)
        _ys = [v.co.y * 1000 for v in new_ring]
        if si == 1 or si == _NB:
            print(f"[{side}] 环{si}/{_NB} s={s_k:.2f} y均={sum(_ys)/len(_ys):7.2f} y范围[{min(_ys):7.2f},{max(_ys):7.2f}]", flush=True)
        _rings_built.append(new_ring)
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
        # 2026-09-16 修尖刺: 极点y必须与末环连续. 参考碗中心射线(r≈0)非单调(实测r=2mm处-87.6, r=0处回弹-82.9),
        # 直接用会造出朝前4.7mm的圆锥尖(用户截图报的'放射状尖刺'). 改为末环平面+0.2mm微凸, 圆滑收口.
        # 2026-09-17 v18: 极点 = 眼窝心平面再深 POLE_STEP(参考碗实测+2.17mm); 末环已全平, 扇面天然连续
        _py = _y_deep + _POLE_STEP
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
# ---- v19(用户: 眼球要在02输出中出现, 后续UV/烘焙/绑定/导出全程连贯) ----
# 把01_2里的眼球对象(Eye002_L/R)并入本文件(保持世界位置; 只并入眼球, 不带高模)
try:
    _existing = [o for o in bpy.data.objects if o.name.startswith('Eye002')]
    if not _existing:
        with bpy.data.libraries.load(EYE_BLEND) as (_src, _dst):
            _dst.objects = [n for n in _src.objects if n.startswith('Eye002')]
        _eyes = [o for o in _dst.objects if o is not None]
        for _o in _eyes:
            bpy.context.scene.collection.objects.link(_o)
        print(f"眼球并入: {[o.name for o in _eyes]}")
    else:
        print(f"眼球已存在, 跳过: {[o.name for o in _existing]}")
except Exception as _e:
    print(f"眼球并入失败: {_e}")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)
