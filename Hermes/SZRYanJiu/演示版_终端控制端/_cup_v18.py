# -*- coding: utf-8 -*-
"""v18: 碗构造 = 用户真实方法(实测其参考碗反推) — 纯线性插值到全平"眼窝心"环.
规律(参考碗逐环实测): 深度步进+3.13×7全等; 波动衰减(8-k)/8; 最深环全平(std=0) ; 极点再深+2.17mm.
"""
import ast
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\02QR拓扑\scripts\02qr_socket_cup.py"
s = open(P, encoding="utf-8").read()
R = []

def rep(old, new, tag):
    global s
    assert old in s, f"未匹配: {tag}"
    s = s.replace(old, new, 1)
    R.append(tag)

# 1) 缩放序列 → 线性步进到 _S_DEEP
rep("""    _SCALES = [0.90, 0.80, 0.70, 0.59, 0.48, 0.37, 0.26, 0.15]
    _NB = len(_SCALES)""",
"""    # 2026-09-17 v18 用户口径: rim→最深环【线性】缩放(参考碗实测每环缩放步进恒定)
    _S_DEEP = 0.152          # 最深环(眼窝心)半径比 = 参考碗实测 0.153
    _NB = 8
    _SCALES = [1.0 - (1.0 - _S_DEEP) * (k / _NB) for k in range(1, _NB + 1)]""", "1 SCALES")

# 2) 深度块 → 线性插值参数
rep("""    # ---- 2026-09-17 用户定案: 复刻用户做法, 深度自算(不看眼球/不采样参考件) ----
    # 用户方法: rim环→沿Y挤出→缩放成眼窝最深处的环→沿Y打平→再挤一点→合并到中心.
    # 深度 D = 0.31×eye_w (用户手调参考碗实测: 总深 11.5mm @ 眼宽 37.13mm; 随尺寸随动)
    # 逐环深度剖面(参考碗实测样条, t=该环相对 rim 的径向比值):
    #   t:   1.00  0.90  0.80  0.70  0.59  0.48  0.37  0.26  0.15  0.00
    #   d/D: 0.00  0.005 0.015 0.03  0.10  0.19  0.33  0.51  0.80  1.00
    _D = 0.67 * float(J[side].get('width_mm', 37.0)) / 1000.0  # 0.67 = 表面比对两轮实测反推(与用户参考碗对齐 |Δy|<2mm)
    # 剖面 t:   1.00  0.90  0.80  0.70  0.59  0.48  0.37  0.26  0.15  0.00
    # d/D:      0.00  0.06  0.10  0.16  0.27  0.40  0.50  0.74  0.98  1.10
    _prof_t = np.array([0.00, 0.15, 0.26, 0.37, 0.48, 0.59, 0.70, 0.80, 0.90, 1.00])
    _prof_d = np.array([1.10, 0.98, 0.80, 0.57, 0.49, 0.34, 0.16, 0.10, 0.06, 0.00])
    _rim_y = [v.co.y for v in ring_v]
    # 2026-09-17 关键(实测用户参考碗得出): rim 在内外眼角比睑缘深 10~20mm, 该深陷【不能】原样带进碗;
    # 用户参考碗的深部 = 睑缘基线 + 深度, 角部只余少量衰减影响 → 基线用中位数, 角部偏差按 λ 衰减.
    _y_base = float(np.median(_rim_y))
    _LAM_BASE = 0.52
    def _depth_of(s_k):
        return _D * float(np.interp(s_k, _prof_t, _prof_d))
    def _lam_of(s_k):
        return _LAM_BASE * (0.70 + 0.30 * s_k)   # 越深衰减越强(浅圈保留较多睑形)""",
"""    # ---- 2026-09-17 v18 用户口径(实测其参考碗反推 = 纯线性插值, 无任何非线性剖面) ----
    # 用户方法: rim环 → 缩放+Y轴打平成"眼窝心"环(最深环, 全平) → 中间均匀分段(Ctrl+R) → 再挤一点合并中心.
    # 参考碗逐环实测: 深度步进 +3.13mm×7 全等; 波动线性衰减 (8-k)/8×rim波动; 最深环 std=0(全平); 极点再深+2.17mm.
    # 实现 = y_k_i = (1-t_k)·rim_y_i + t_k·y_deep, t_k = k/8 → k=8 时恰好全平.
    # y_deep(眼窝心平面) = rim_y均值 + 0.662×eye_w (参考碗实测 24.6mm @ 37.13mm; 随尺寸随动)
    _rim_y = [v.co.y for v in ring_v]
    _eye_w = float(J[side].get('width_mm', 37.0)) / 1000.0
    _y_deep = float(np.mean(_rim_y)) + 0.662 * _eye_w
    _POLE_STEP = 0.058 * _eye_w
    def _t_of(s_k):
        return (1.0 - s_k) / max(1e-9, (1.0 - _S_DEEP))
    def _y_of(s_k, _i):
        _t = _t_of(s_k)
        return (1.0 - _t) * _rim_y[_i] + _t * _y_deep""", "2 深度块")

# 3) _ring_at 的 y2
rep("""            # 复刻用户做法: 基线(rim中位防角部外泄) + 深度剖面 + 角部偏差衰减(λ)
            y2 = _y_base + _depth_of(s_k) + _lam_of(s_k) * (_rim_y[_i] - _y_base)""",
"""            # v18 用户口径: rim_y 线性插值到眼窝心平面
            y2 = _y_of(s_k, _i)""", "3 _ring_at")

# 4) 建环循环的 y2
rep("""            # 复刻用户做法: 基线 + 深度剖面 + 角部衰减(不看眼球/不采样参考件)
            y2 = _y_base + _depth_of(s_k) + _lam_of(s_k) * (_rim_y[_i] - _y_base)""",
"""            # v18 用户口径: rim_y 线性插值到眼窝心平面(末环全平)
            y2 = _y_of(s_k, _i)""", "4 建环")

# 5) 删 v17 二次打平块(线性插值已含精确衰减, 再打平会破坏规律)
rep("""        # ---- v17(用户方法: 挤出→缩放→'沿Y打平'→合并中心) ----
        # 参考实测: 同圈 y 波动被系统压小, 越深越平(深部 ≈0.65×, 外圈 ≈0.96×) → 分深度渐进的打平系数
        _lam = 1.0 - 0.35 * (si / max(_NB, 1))       # 0.956(外) → 0.65(深)
        _ys = [v.co.y for v in new_ring]
        _ym = sum(_ys) / len(_ys)
        for v in new_ring:
            v.co.y = _ym + _lam * (v.co.y - _ym)
        if si == 1:
            print(f"[{side}] v17 打平: 圈1 λ={_lam:.3f} … 末圈 λ={1.0-0.35*(_NB/max(_NB,1)):.3f}", flush=True)
""", "", "5 删v17打平")

# 6) 极点 y
rep("""        # 2026-09-17: 极点取末环【最靠后(/最大y)】+0.5mm — 均值会落进环内导致扇面翻折
        _py = float(max(v.co.y for v in last_ring)) + 0.0005""",
"""        # 2026-09-17 v18: 极点 = 眼窝心平面再深 POLE_STEP(参考碗实测+2.17mm); 末环已全平, 扇面天然连续
        _py = _y_deep + _POLE_STEP""", "6 极点")

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("已应用:", R, flush=True)

# 残留检查
leftover = [l for l in s.splitlines() if ("_depth_of" in l or "_lam_of" in l or "_y_base" in l or "_prof_" in l)]
print("残留引用:", leftover if leftover else "无 ✓", flush=True)
