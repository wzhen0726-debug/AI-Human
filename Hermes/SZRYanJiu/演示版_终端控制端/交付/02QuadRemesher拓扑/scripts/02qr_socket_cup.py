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
        ctr = co.mean(axis=0)
        # v2: 用【最大半径】(含角膜凸起)而非平均 → 碗面把整个眼球+角膜都包住
        rad = float(np.linalg.norm(co - ctr, axis=1).max())
        s = "L" if ctr[0] < 0 else "R"
        BALL[s] = (Vector(tuple(ctr)), rad)
        print(f"眼球[{s}]: 球心({ctr[0]*1000:.1f},{ctr[1]*1000:.1f},{ctr[2]*1000:.1f})mm 半径{rad*1000:.2f}mm")
CLR = 0.0015   # 碗面与球面的间隙(眼球后极不穿碗底)

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
SCALES = [0.92, 0.84, 0.75, 0.65, 0.54, 0.42, 0.29, 0.15]   # 0.15 小内圈保证平底盖尽量贴近球后极深度(眼球后极+间隙)

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
    # 各点极坐标(相对眼中心 XZ)
    polar = []
    for v in ring_v:
        dx, dz = v.co.x - bx, v.co.z - bz
        polar.append((math.hypot(dx, dz), math.atan2(dz, dx)))
    CAP_N = M            # 最内圈点数
    last_ring = ring_v
    made = 0
    _new_faces = []
    for si, s in enumerate(SCALES, start=1):
        new_ring = []
        for (r, th) in polar:
            r2 = r * s
            y2 = yc + math.sqrt(max(0.0, (R + CLR) ** 2 - r2 * r2))
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            v2 = bm.verts.new(Vector((x2, y2, z2)))
            new_ring.append(v2)
        bm.verts.ensure_lookup_table()
        for i in range(len(last_ring)):
            a = last_ring[i]; b = last_ring[(i + 1) % len(last_ring)]
            c = new_ring[(i + 1) % len(new_ring)]; dv = new_ring[i]
            try:
                _nf = bm.faces.new((a, b, c, dv)); _nf[_tag] = 1; _new_faces.append(_nf); made += 1
            except Exception:
                try:
                    _nf = bm.faces.new((a, c, b, dv)); _nf[_tag] = 1; _new_faces.append(_nf); made += 1
                except Exception:
                    pass
        last_ring = new_ring
    # ---- ③ 最内圈用单 n-gon 封底 ----
    try:
        _f2 = bm.faces.new(last_ring); _f2[_tag] = 1; _new_faces.append(_f2); made += 1
        print(f"[{side}] 底部 n-gon 盖 {len(last_ring)} 边")
    except Exception as _e:
        print(f"[{side}] n-gon 盖失败: {_e}")
    # ---- 只对本次新建的碗面定向(凹面: 法线应指向眼球中心); 引用此刻有效 ----
    _ball_c = Vector((bx, yc, bz))
    _fx = 0
    for _f in _new_faces:
        try:
            _n = _f.normal
            _to_ball = _ball_c - _f.calc_center_median()
            if _n.length > 1e-12 and _to_ball.length > 1e-9 and _n.dot(_to_ball) < 0:
                _f.normal_flip(); _fx += 1
        except ReferenceError:
            pass
    bm.normal_update()
    print(f"[{side}] 新建面 {made} (定向翻转 {_fx})")

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
