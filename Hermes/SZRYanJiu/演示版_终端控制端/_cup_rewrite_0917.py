# -*- coding: utf-8 -*-
"""2026-09-17 用户定案: 碗工序深度改为【复刻用户做法】—— 不看眼球、不采样参考件.
用户方法: rim环 → 沿Y挤出 → 缩放成眼窝最深处的环 → 沿Y打平 → 再挤一点 → 合并中心.
深度自算: D = 0.31×eye_w (由用户手调参考碗实测总深 11.5mm@眼宽37.13mm 反推, 随尺寸随动);
逐环深度剖面 = 参考碗实测样条 (t=环比值): 1.0→0 / 0.48→0.19 / 0.37→0.33 / 0.26→0.51 / 0.15→0.80 / 0→1.0.
实现 = 每环 y = 对应rim顶点的y + D·剖面(t)  (rim的Y形状随环带下去, 再由原有的λ打平压匀)。
"""
import ast, re
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\02QR拓扑\scripts\02qr_socket_cup.py"
s = open(P, encoding="utf-8").read()

# ---- 1) 插入深度定义(在 _SCALES/_NB 定义之后) ----
anchor = "    _NB = len(_SCALES)\n"
assert anchor in s
ins = anchor + '''
    # ---- 2026-09-17 用户定案: 复刻用户做法, 深度自算(不看眼球/不采样参考件) ----
    # 用户方法: rim环→沿Y挤出→缩放成眼窝最深处的环→沿Y打平→再挤一点→合并到中心.
    # 深度 D = 0.31×eye_w (用户手调参考碗实测: 总深 11.5mm @ 眼宽 37.13mm; 随尺寸随动)
    # 逐环深度剖面(参考碗实测样条, t=该环相对 rim 的径向比值):
    #   t:   1.00  0.90  0.80  0.70  0.59  0.48  0.37  0.26  0.15  0.00
    #   d/D: 0.00  0.005 0.015 0.03  0.10  0.19  0.33  0.51  0.80  1.00
    _D = 0.31 * float(J[side].get('width_mm', 37.0)) / 1000.0
    _prof_t = np.array([0.00, 0.15, 0.26, 0.37, 0.48, 0.59, 0.70, 0.80, 0.90, 1.00])
    _prof_d = np.array([1.00, 0.80, 0.51, 0.33, 0.19, 0.10, 0.03, 0.015, 0.005, 0.00])
    _rim_y = [v.co.y for v in ring_v]
    def _depth_of(s_k):
        return _D * float(np.interp(s_k, _prof_t, _prof_d))
'''
s = s.replace(anchor, ins, 1)

# ---- 2) _ring_at 里的 y2 ----
old_at = '''    def _ring_at(s_k):
        out = []
        for (r, th) in polar:
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            y2 = None
            if side in REF_BVH:
                _hit = REF_BVH[side].ray_cast(Vector((x2, c3.y - 0.060, z2)), Vector((0.0, 1.0, 0.0)))
                if _hit and _hit[0] is not None:
                    y2 = float(_hit[0][1])
            if y2 is None:
                y2 = yc + math.sqrt(max(0.0, (R + CLR) ** 2 - r2 * r2))
            out.append(Vector((x2, y2, z2)))
        return out'''
new_at = '''    def _ring_at(s_k):
        out = []
        for _i, (r, th) in enumerate(polar):
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            # 复刻用户做法: 沿Y挤出+缩放 → y = rim该点y + 深度剖面(该环) — 不再采样参考件/球面
            y2 = _rim_y[_i] + _depth_of(s_k)
            out.append(Vector((x2, y2, z2)))
        return out'''
assert old_at in s, "1 _ring_at未匹配"
s = s.replace(old_at, new_at, 1)

# ---- 3) 建环循环里的 y2 ----
old_loop = '''        for (r, th) in polar:
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            # 深度: 优先从高模旧碗面射线采样(用户要求的'之前的形状'); 回退=同心球+间隙
            y2 = None
            if side in REF_BVH:
                _hit = REF_BVH[side].ray_cast(Vector((x2, c3.y - 0.060, z2)), Vector((0.0, 1.0, 0.0)))
                if _hit and _hit[0] is not None:
                    y2 = float(_hit[0][1])
            if y2 is None:
                y2 = yc + math.sqrt(max(0.0, (R + CLR) ** 2 - r2 * r2))
            v2 = bm.verts.new(Vector((x2, y2, z2)))
            new_ring.append(v2)'''
new_loop = '''        for _i, (r, th) in enumerate(polar):
            r2 = max(r * s_k, 0.001)
            x2 = bx + r2 * math.cos(th)
            z2 = bz + r2 * math.sin(th)
            # 复刻用户做法: 沿Y挤出+缩放 → y = rim该点y + 深度剖面(该环) — 不看眼球/不采样参考件
            y2 = _rim_y[_i] + _depth_of(s_k)
            v2 = bm.verts.new(Vector((x2, y2, z2)))
            new_ring.append(v2)'''
assert old_loop in s, "2 建环循环未匹配"
s = s.replace(old_loop, new_loop, 1)

# ---- 4) 删除焊接块(用户做法没有焊接; 结构保持纯净) ----
weld_pat = re.compile(r"    # ---- 2026-09-16 修复极点尖刺.*?\n(.*?\n)*?        print\(f\"\[\{side\}\] 深部焊接.*?\n\n", re.M)
m = weld_pat.search(s)
if m:
    s = s[:m.start()] + s[m.end():]
    print("[✓] 焊接块已删", flush=True)
else:
    print("[⚠] 焊接块未匹配到(需人工检查)", flush=True)

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("CUP_DEPTH_REWRITE_DONE", flush=True)
# 残留检查
for i, ln in enumerate(s.splitlines(), 1):
    if "REF_BVH" in ln and "ray_cast" in ln:
        print(f"  [残留ray_cast] L{i}: {ln.strip()[:80]}", flush=True)
