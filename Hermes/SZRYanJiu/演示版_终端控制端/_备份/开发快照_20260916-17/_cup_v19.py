# -*- coding: utf-8 -*-
"""v19: 碗脚本 — ① 深度/环密度全部程序化计算(基于 rim 自身几何 r_ref) ② 彻底去除对眼球的依赖(纯rim)."""
import ast
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\02QR拓扑\scripts\02qr_socket_cup.py"
s = open(P, encoding="utf-8").read()
R = []
def rep(old, new, tag):
    global s
    assert old in s, f"未匹配: {tag}"
    s = s.replace(old, new, 1); R.append(tag)

# 1) 头注
rep('''"""02 QR 之后: 低模碗状眼窝重建(眼球坐进去).
2026-09-16 用户确认方向: "在低模上重建碗状眼窝(有碗面, 眼球坐进去)".

做法(全部随动, 无硬编码):
  ① 从 01_2 的真实眼球对象推导: 球心 yc(xz 与眼中心一致)、半径 R、间隙 clr(默认 0.0015m)
  ② 每个眼孔边界环(QR 输出的开放边界闭环) → 内收 N 圈; 第 k 圈半径 = 原半径×s_k,
     深度按【眼球同心球面+间隙】取值: y = yc + sqrt(max(0,(R+clr)^2 - r'^2))
     → 碗面天然包住眼球, 不穿球
  ③ 最内圈用小 n-gon 封底(旧版验证过: 单极点三角扇有放射条纹, 单 n-gon 盖干净)
  ④ smooth shading; 保存为新文件(不覆盖 02_qr_150k.blend)

输出: 02QR拓扑/输出/02_qr_150k_socket.blend
"""''',
'''"""02 QR 之后: 低模碗状眼窝重建(复刻用户手工方法, 纯 rim 几何, 不看眼球).
2026-09-17 用户口径: "没补洞(QR原样)没问题; 按我那个方案做眼窝——先根据 rim 做一个
  Y轴打平的'眼窝心'环, 中间加均匀分段; 深度/密度都要算出来, 不做死参数; 不去管眼珠."

做法(全部程序化, 无绝对mm):
  ① 每个眼孔边界环(QR 输出开放边界闭环) = rim
  ② 几何基准 r_ref = rim 顶点到眼心的 XZ 距离中位数(开口等效半径, 现场测量)
  ③ 碗深 D = 2.264×r_ref; 分段步进 = 0.283×r_ref; 环数 n = round(D/步进) 夹5..12 (=8);
     最深环(眼窝心)半径比 0.152(无量纲), 全平; 极点再深 0.196×r_ref
     (五组系数 = 用户手调参考碗逐环实测反推, 见 方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/)
  ④ 中间 = 线性插值 y_k_i=(1-t_k)·rim_y_i + t_k·y_deep, t_k=k/n → 末环恰好全平
  ⑤ 极点收口 + smooth; 保存为正典产物
  ⑥ 眼球由 run_eyeball_v2 在其后摆入并并入本输出(本脚本不接触眼球)

输出: 02QR拓扑/输出/02_qr_150k_socket.blend
"""''', "1 头注")

# 2) 删 EYE_BLEND 行
rep('''EYE_BLEND = os.path.join(D, "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")
OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")''',
'''OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")''', "2 EYE_BLEND")

# 3) 删 BALL 载入 + REF 载入 两大块
i0 = s.find("# ---- ① 从 01_2 拿真实眼球的球心/半径 ----")
i1 = s.find('    print(f"⚠ 参考件不存在({os.path.basename(REF_BLEND)}), 将用眼球同心球剖面")')
assert i0 > 0 and i1 > i0, "3 定位失败"
i1 = s.find("\n", i1) + 1
s = s[:i0] + "# (2026-09-17 v19 移除: 眼球载入(BALL) 与 旧参考件(_eye_cup_ref)载入 — 碗=纯 rim 几何)\n\n" + s[i1:]
R.append("3 删BALL/REF载入")

# 4) 循环头: 去 BALL 检查, 轴心改轮廓中心
rep('''for side in ("L", "R")):
    c3 = Vector(tuple(float(x) for x in J[side]['center']))
    if side not in BALL:
        print(f"[{side}] 01_2 里没找到眼球, 跳过")
        continue
    _bc = BALL[side][0]
    yc, R = _bc[1], BALL[side][1]
    bx, bz = _bc[0], _bc[2]     # ★以【眼球中心】为碗的轴心(轮廓中心与球心差~1.4mm, 直接用会吃掉间隙)'''.replace(')):', '):'),
'''for side in ("L", "R"):
    c3 = Vector(tuple(float(x) for x in J[side]['center']))
    # v19: 轴心 = 轮廓自身中心(x,z) — 不再依赖眼球
    bx, bz = float(c3.x), float(c3.z)''', "4 循环头")

# 5) 建碗打印
rep('''    print(f"[{side}] 孔环 {M} 点 → 建碗(球心y{yc*1000:.1f} 半径{R*1000:.2f} 间隙{CLR*1000:.1f}mm)")''',
'''    print(f"[{side}] 孔环 {M} 点 → 建碗")''', "5 建碗打印")

# 6) SCALES 块 → 方法化
rep('''    # 2026-09-17 v18 用户口径: rim→最深环【线性】缩放(参考碗实测每环缩放步进恒定)
    _S_DEEP = 0.152          # 最深环(眼窝心)半径比 = 参考碗实测 0.153
    _NB = 8
    _SCALES = [1.0 - (1.0 - _S_DEEP) * (k / _NB) for k in range(1, _NB + 1)]''',
'''    # 2026-09-17 v19 方法化(用户要求"算出来, 不做死参数"; 系数=参考碗实测反推, 全部无量纲随动):
    #   r_ref = rim 顶点到眼心的 XZ 距离中位数(开口等效半径)
    #   D (碗深)      = 2.264 × r_ref
    #   步进(决定环密度) = 0.283 × r_ref
    #   n (环数)      = round(D/步进), 夹 5..12
    _r_ref = float(np.median([r for (r, th) in polar]))
    _D_socket = 2.264 * _r_ref
    _step_ref = 0.283 * _r_ref
    _NB = int(np.clip(round(_D_socket / _step_ref), 5, 12))
    _S_DEEP = 0.152          # 最深环(眼窝心)半径比(无量纲, 参考碗实测)
    _SCALES = [1.0 - (1.0 - _S_DEEP) * (k / _NB) for k in range(1, _NB + 1)]''', "6 SCALES")

# 7) 深度块 → r_ref 计算 + 打印
rep('''    # ---- 2026-09-17 v18 用户口径(实测其参考碗反推 = 纯线性插值, 无任何非线性剖面) ----
    # 用户方法: rim环 → 缩放+Y轴打平成"眼窝心"环(最深环, 全平) → 中间均匀分段(Ctrl+R) → 再挤一点合并中心.
    # 参考碗逐环实测: 深度步进 +3.13mm×7 全等; 波动线性衰减 (8-k)/8×rim波动; 最深环 std=0(全平); 极点再深+2.17mm.
    # 实现 = y_k_i = (1-t_k)·rim_y_i + t_k·y_deep, t_k = k/8 → k=8 时恰好全平.
    # y_deep(眼窝心平面) = rim_y均值 + 0.662×eye_w (参考碗实测 24.6mm @ 37.13mm; 随尺寸随动)
    _rim_y = [v.co.y for v in ring_v]
    _eye_w = float(J[side].get('width_mm', 37.0)) / 1000.0
    _y_deep = float(np.mean(_rim_y)) + 0.675 * _eye_w  # 0.675 = 参考碗 deepest ring 绝对y对齐实测反推
    _POLE_STEP = 0.058 * _eye_w''',
'''    # ---- 2026-09-17 v19 用户方法(实测其参考碗反推 = 纯线性插值; 深度/密度全部算出来) ----
    # 用户方法: rim环 → 缩放+Y轴打平成"眼窝心"环(最深环, 全平) → 中间均匀分段 → 再挤一点合并中心.
    # 参考碗逐环实测: 深度步进全等; 波动线性衰减 (n-k)/n×rim波动; 最深环 std=0(全平); 极点再深≈2.17mm.
    # 实现 = y_k_i = (1-t_k)·rim_y_i + t_k·y_deep, t_k = k/n → 末环恰好全平.
    _rim_y = [v.co.y for v in ring_v]
    _y_deep = float(np.mean(_rim_y)) + _D_socket          # 眼窝心平面(全平)
    _POLE_STEP = 0.196 * _r_ref
    print(f"[{side}] 碗参数(自算): r_ref={_r_ref*1000:.2f}mm 深D={_D_socket*1000:.2f}mm "
          f"步进={_step_ref*1000:.2f}mm 环数={_NB} 极点再深={_POLE_STEP*1000:.2f}mm", flush=True)''', "7 深度块")

# 8) 删眼球并入尾块
i0 = s.find("# ---- v19(用户: 眼球要在02输出中出现")
i1 = s.find('    print(f"眼球并入失败: {_e}")')
assert i0 > 0 and i1 > i0, "8 定位失败"
i1 = s.find("\n", i1) + 1
s = s[:i0] + '''# 2026-09-17 流程变更(用户): 眼球摆入挪到【碗之后】(碗=纯rim几何, 不看眼球);
# 眼球并入改由 run_eyeball_v2 在摆入完成后进行 → 本脚本不再接触眼球。
''' + s[i1:]
R.append("8 删并入尾块")

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("碗脚本 v19 已应用:", R, flush=True)
left = [l for l in s.splitlines() if ("BALL" in l or "REF_BVH" in l or "EYE_BLEND" in l or "CLR" in l or " yc" in l)]
print("残留:", left if left else "无 ✓", flush=True)
