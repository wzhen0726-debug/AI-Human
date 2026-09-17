# -*- coding: utf-8 -*-
"""02 QR 之后: 低模碗状眼窝重建(复刻用户手工方法, 纯 rim 几何, 不看眼球).
2026-09-17 用户口径: "没补洞(QR原样)没问题; 按我那个方案做眼窝——先根据 rim 做一个
  Y轴打平的'眼窝心'环, 中间加均匀分段; 深度/密度都要算出来, 不做死参数; 不去管眼珠."

做法(全部程序化, 无绝对mm):
  ① 每个眼孔边界环(QR 输出开放边界闭环) = rim
  ② 几何基准 r_ref = rim 顶点到眼心的 XZ 距离中位数(开口等效半径, 现场测量)
  ③ 碗深 D = 2.04×r_ref; 分段步进 = 0.255×r_ref; 环数 n = round(D/步进) 夹5..12 (=8);
     最深环(眼窝心)半径比 0.152(无量纲), 全平; 极点再深 0.176×r_ref
     (五组系数 = 用户手调参考碗逐环实测反推, 见 方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/)
  ④ 中间 = 线性插值 y_k_i=(1-t_k)·rim_y_i + t_k·y_deep, t_k=k/n → 末环恰好全平
  ⑤ 极点收口 + smooth; 保存为正典产物
  ⑥ 眼球由 run_eyeball_v2 在其后摆入并并入本输出(本脚本不接触眼球)

输出: 02QR拓扑/输出/02_qr_150k_socket.blend
"""
import bpy, os, json, math, numpy as np, bmesh
import functools
print = functools.partial(print, flush=True)   # 日志实时可见(定位卡点)
from mathutils import Vector

D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
QR_BLEND = os.path.join(D, "02QR拓扑", "_中间", "02_qr_150k.blend")
OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
J = json.load(open(os.path.join(D, "01a眼窝眼球", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))

# (2026-09-17 v19 移除: 眼球载入(BALL) 与 旧参考件(_eye_cup_ref)载入 — 碗=纯 rim 几何)


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
    # v19: 轴心 = 轮廓自身中心(x,z) — 不再依赖眼球
    bx, bz = float(c3.x), float(c3.z)
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
    print(f"[{side}] 孔环 {M} 点 → 建碗")
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
    # 2026-09-17 v19 方法化(用户要求"算出来, 不做死参数"; 系数=参考碗实测反推, 全部无量纲随动):
    #   r_ref = rim 顶点到眼心的 XZ 距离中位数(开口等效半径)
    #   D (碗深)      = 2.04 × r_ref
    #   步进(决定环密度) = 0.255 × r_ref
    #   n (环数)      = round(D/步进), 夹 5..12
    _r_ref = float(np.median([r for (r, th) in polar]))
    _D_socket = 2.04 * _r_ref
    _step_ref = 0.255 * _r_ref
    _NB = int(np.clip(round(_D_socket / _step_ref), 5, 12))
    _S_DEEP = 0.152          # 最深环(眼窝心)半径比(无量纲, 参考碗实测)
    _SCALES = [1.0 - (1.0 - _S_DEEP) * (k / _NB) for k in range(1, _NB + 1)]

    # ---- 2026-09-17 v19 用户方法(实测其参考碗反推 = 纯线性插值; 深度/密度全部算出来) ----
    # 用户方法: rim环 → 缩放+Y轴打平成"眼窝心"环(最深环, 全平) → 中间均匀分段 → 再挤一点合并中心.
    # 参考碗逐环实测: 深度步进全等; 波动线性衰减 (n-k)/n×rim波动; 最深环 std=0(全平); 极点再深≈2.17mm.
    # 实现 = y_k_i = (1-t_k)·rim_y_i + t_k·y_deep, t_k = k/n → 末环恰好全平.
    _rim_y = [v.co.y for v in ring_v]
    _y_deep = float(np.mean(_rim_y)) + _D_socket          # 眼窝心平面(全平)
    _POLE_STEP = 0.176 * _r_ref
    print(f"[{side}] 碗参数(自算): r_ref={_r_ref*1000:.2f}mm 深D={_D_socket*1000:.2f}mm "
          f"步进={_step_ref*1000:.2f}mm 环数={_NB} 极点再深={_POLE_STEP*1000:.2f}mm", flush=True)
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
# 2026-09-17 流程变更(用户): 眼球摆入挪到【碗之后】(碗=纯rim几何, 不看眼球);
# 眼球并入改由 run_eyeball_v2 在摆入完成后进行 → 本脚本不再接触眼球。

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)
