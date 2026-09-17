# -*- coding: utf-8 -*-
"""控制台: ① step_02 重排(QR→碗→眼球摆入+并入) ② 文案更新 ③ clean 重写(修复丢失的①②逻辑+NameError)."""
import ast
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\控制台.py"
s = open(P, encoding="utf-8").read()
R = []
def rep(old, new, tag):
    global s
    assert old in s, f"未匹配: {tag}"
    s = s.replace(old, new, 1); R.append(tag)

# 1) 头注
rep("  ⑦ (2026-09-16) 眼球摆入从01a挪到02(QR之后,碗之前)",
    "  ⑦ (2026-09-17) 眼球摆入在02的【碗之后】(QR → 碗(纯rim) → 眼球摆入并并入输出)", "1 头注")

# 2) step_02 标题/细分
rep('''    print(f"{Y}{BOLD}▶ 环节 02 · 拓扑重建 + 眼球摆入 + 眼窝碗{W}")
    print(f"{D}  细分: QR自动拓扑 → 眼球摆入(角膜自动测量) → 眼窝碗(按眼球反推) · 引导=眼窝独立材质{W}\\n")''',
'''    print(f"{Y}{BOLD}▶ 环节 02 · 拓扑重建 + 眼窝碗 + 眼球摆入{W}")
    print(f"{D}  细分: QR自动拓扑 → 眼窝碗(纯rim程序化: 深度/环数自算) → 眼球摆入(并并入输出) · 碗不含眼球几何{W}\\n")''', "2 step02标题")

# 3) step_02 执行顺序
rep('''    # 2026-09-16 用户: 眼球摆入挪到 QR 之后(碗依赖眼球真值, 仍在此之前)
    if not run_blender(os.path.join(S01A, "run_eyeball_v2.py"), "02_眼球", "眼球摆入(角膜自动测量+Hazel)"):
        summary("环节 02", False, t0, []); return False
    # 眼窝碗重建(按眼球反推+打平+极点收口) — 正典产物=带碗版
    if not run_blender(os.path.join(BASE, "02QR拓扑", "scripts", "02qr_socket_cup.py"),
                       "02_碗", "眼窝碗重建(按眼球几何, 非穿透)", done_mark="SAVED:"):
        summary("环节 02", False, t0, []); return False''',
'''    # 2026-09-17 用户新流程: 碗=纯 rim 几何(不看眼球) → 眼球在碗之后摆入, 并并入碗输出
    if not run_blender(os.path.join(BASE, "02QR拓扑", "scripts", "02qr_socket_cup.py"),
                       "02_碗", "眼窝碗重建(纯rim: 深度/环数自算)", done_mark="SAVED:"):
        summary("环节 02", False, t0, []); return False
    if not run_blender(os.path.join(S01A, "run_eyeball_v2.py"), "02_眼球",
                       "眼球摆入(角膜自动测量, 并并入碗输出)"):
        summary("环节 02", False, t0, []); return False''', "3 step02顺序")

# 4) status 标签
rep('("02 眼球(QR后摆入)", "01a眼窝眼球/输出/01_2_eyeball_placed.blend"),',
    '("02 眼球(碗后摆入)", "01a眼窝眼球/输出/01_2_eyeball_placed.blend"),', "4 status标签")

# 5) clean 重写(当前残缺: targets后缺①②逻辑, 且 n 未初始化)
i0 = s.find("    targets = {\n        \"01\": os.path.join(BASE, \"01高模修复\", \"输出\"),")
i1 = s.find('    print(f"\\n{G}★ 清理完成, 共删除 {n} 项{W}")')
assert i0 > 0 and i1 > i0, "5 定位失败"
i1 = s.find("\n", i1) + 1
new_clean = '''    targets = {
        "01": os.path.join(BASE, "01高模修复", "输出"),
        "01a": os.path.join(BASE, "01a眼窝眼球", "输出"),
        "02": os.path.join(BASE, "02QR拓扑", "输出"),
        "03": os.path.join(BASE, "03自动UV", "输出"),
        "04": os.path.join(BASE, "04纹理烘焙", "输出"),
        "05": os.path.join(BASE, "05骨骼绑定", "输出"),
    }
    PROTECT = ("01A_markers_eyelid.blend", "eyelid_contour_manual.json", "iris_3ddfa.json",
               "eyeball_finetune_manual.json", ".gitkeep")
    def _wipe(d):
        cnt = 0
        if not os.path.isdir(d):
            return 0
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                if f in PROTECT or f.startswith("01A_markers_eyelid_备份_"):
                    continue
                try: os.remove(os.path.join(root, f)); cnt += 1
                except Exception: pass
            for dd in dirs:
                try: os.rmdir(os.path.join(root, dd)); cnt += 1
                except Exception: pass
        return cnt
    if target in (None, "all"):
        sel = list(targets.keys())
    elif target in targets:
        sel = [target]
    else:
        print(f"{R}✗ 未知环节: {target} (可选: 01/01a/02/03/04/05/all){W}"); show_hint(); return
    n = 0
    for t in sel:
        n += _wipe(targets[t])                                              # ① 输出/ 递归清空(保留手调文件)
        n += _wipe(os.path.join(os.path.dirname(targets[t]), "_中间"))       # ② _中间/ 一并清(防下游读旧件)
    n += _wipe(os.path.join(BASE, "01a眼窝眼球", "screenshots"))
    import glob as _glob
    for d in [os.path.join(BASE, "01高模修复"), os.path.join(BASE, "01a眼窝眼球"),
              os.path.join(BASE, "01a眼窝眼球", "_中间"),
              os.path.join(BASE, "02QR拓扑"), os.path.join(BASE, "03自动UV"),
              os.path.join(BASE, "04纹理烘焙"), os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")]:
        for pat in ("*.blend1", "01A_markers_eyelid_备份_*.blend"):
            for fp in _glob.glob(os.path.join(d, pat)):
                try: os.remove(fp); n += 1
                except Exception: pass
    print(f"\\n{G}★ 清理完成, 共删除 {n} 项{W}")
'''
s = s[:i0] + new_clean + s[i1:]
R.append("5 clean重写")

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("控制台 已应用:", R, flush=True)
# 残留检查
left = [f"L{i}:{l.strip()[:70]}" for i, l in enumerate(s.splitlines(), 1) if ("按眼球" in l or "眼球真值" in l or "QR之后" in l)]
print("残留:", left if left else "无 ✓", flush=True)
