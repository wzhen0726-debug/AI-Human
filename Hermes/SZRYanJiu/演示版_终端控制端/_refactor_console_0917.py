# -*- coding: utf-8 -*-
"""2026-09-17 控制台.py 精细改造: 去掉 交付/ 概念, 产物直接读写各 stage 的 输出/ (用户约定)."""
import ast

P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\控制台.py"
s = open(P, encoding="utf-8").read()

REPS = [
 # 1) 版本注记
 ("  ⑦ (2026-09-16) 眼球摆入从01a挪到02(QR之后,碗之前); clean改递归+清交付生成物; 交付=正典, 中间件收_中间/",
  "  ⑦ (2026-09-16) 眼球摆入从01a挪到02(QR之后,碗之前)\n  ⑧ (2026-09-17) 用户: 无交付概念; 测试期产物一律写各stage的 输出/, 中间件收各stage的 _中间/"),
 # 2) 路径定义
 ('DELIVERY = os.path.join(BASE, "交付")',
  'ROOT = BASE  # 2026-09-17 用户: 测试期不搞交付, 产物直接写各stage的 输出/'),
 ('S01A = os.path.join(DELIVERY, "01A眼窝与眼球", "scripts")', 'S01A = os.path.join(BASE, "01a眼窝眼球", "scripts")'),
 ('M01A = os.path.join(DELIVERY, "01A眼窝与眼球", "models")', 'M01A = os.path.join(BASE, "01a眼窝眼球", "输出")'),
 ('S05 = os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831", "scripts")', 'S05 = os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831", "scripts")'),
 ('B05 = os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831")', 'B05 = os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")'),
 # 3) deliver(): 自拷贝保护 + 文案
 ('# ============ 产物统计 / 交付 ============', '# ============ 产物统计 / 投放 ============'),
 ('''    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst):''',
  '''    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.abspath(src) == os.path.abspath(dst):
        sz = os.path.getsize(src) / 1024 / 1024
        print(f"  {G}✓ 产物{W} {os.path.relpath(src, BASE)} {D}({sz:.1f}MB){W}")
        return True
    if os.path.exists(dst):'''),
 ('print(f"  {G}✓ 交付{W} {rel} {D}({sz:.1f}MB){W}")', 'print(f"  {G}✓ 产物{W} {rel} {D}({sz:.1f}MB){W}")'),
 # 4) check()
 ('    return os.path.exists(os.path.join(DELIVERY, rel))', '    return os.path.exists(os.path.join(BASE, rel))'),
 # 5) step_01
 ('out = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")',
  'out = os.path.join(BASE, "01高模修复", "输出", "01_highpoly_repair.blend")'),
 ('script = os.path.join(DELIVERY, "01高模修复与黏连检测", "scripts", "run_repair.py")',
  'script = os.path.join(BASE, "01高模修复", "scripts", "run_repair.py")'),
 # 6) step_01a
 ('if not check("01高模修复与黏连检测/models/01_highpoly_repair.blend"):',
  'if not check("01高模修复/输出/01_highpoly_repair.blend"):'),
 # 7) step_02
 ('if not check("01A眼窝与眼球/models/_中间/01_1_eye_socket_qr.blend"):',
  'if not check("01a眼窝眼球/_中间/01_1_eye_socket_qr.blend"):'),
 ('os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02_qr_auto.py")',
  'os.path.join(BASE, "02QR拓扑", "scripts", "02_qr_auto.py")'),
 ('os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02qr_socket_cup.py")',
  'os.path.join(BASE, "02QR拓扑", "scripts", "02qr_socket_cup.py")'),
 ('qr = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_socket.blend")',
  'qr = os.path.join(BASE, "02QR拓扑", "输出", "02_qr_150k_socket.blend")'),
 ('_pre_src = os.path.join(DELIVERY, "02QuadRemesher拓扑", "_中间", "02_qr_150k.blend")',
  '_pre_src = os.path.join(BASE, "02QR拓扑", "_中间", "02_qr_150k.blend")'),
 ('_pre = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_未补洞_拓扑后.blend")',
  '_pre = os.path.join(BASE, "02QR拓扑", "输出", "02_qr_150k_未补洞_拓扑后.blend")'),
 # 8) step_03
 ('if not check("02QuadRemesher拓扑/02_qr_150k_socket.blend"):', 'if not check("02QR拓扑/输出/02_qr_150k_socket.blend"):'),
 ('os.path.join(DELIVERY, "03自动UV", "scripts", "03_auto_uv.py")', 'os.path.join(BASE, "03自动UV", "scripts", "03_auto_uv.py")'),
 ('out = os.path.join(DELIVERY, "03自动UV", "03_auto_uv.blend")', 'out = os.path.join(BASE, "03自动UV", "输出", "03_auto_uv.blend")'),
 # 9) step_04
 ('if not check("03自动UV/03_auto_uv.blend"):', 'if not check("03自动UV/输出/03_auto_uv.blend"):'),
 ('os.path.join(DELIVERY, "04纹理烘焙", "scripts", "04_bake.py")', 'os.path.join(BASE, "04纹理烘焙", "scripts", "04_bake.py")'),
 ('o = os.path.join(DELIVERY, "04纹理烘焙"); outd = os.path.join(BASE, "04纹理烘焙", "输出")',
  'o = os.path.join(BASE, "04纹理烘焙", "输出"); outd = o'),
 # 10) step_05
 ('if not check("04纹理烘焙/04_bake.blend"):', 'if not check("04纹理烘焙/输出/04_bake.blend"):'),
 # 11) clean: 删掉"交付生成产物"白名单块 + 改 sweep
 ('    """清理输出文件夹(递归) + 交付里的生成产物. target=None/单环节/all',
  '    """清理各stage 输出/ 文件夹(递归) + 中间件 + blend自动备份. target=None/单环节/all'),
 ('                    ②交付里的生成产物也一并清理(否则status一直显示已生成, 且下游读到旧产物)',
  '                    ②各stage _中间/ 也清理(否则下游读到旧产物)'),
 # 12) clean 的 sweep_dirs
 ('''    sweep_dirs = [os.path.join(DELIVERY, "01A眼窝与眼球", "models"),
                  os.path.join(DELIVERY, "02QuadRemesher拓扑"),
                  os.path.join(DELIVERY, "03自动UV"),
                  os.path.join(DELIVERY, "04纹理烘焙"),
                  os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831")]''',
  '''    sweep_dirs = [os.path.join(BASE, "01a眼窝眼球", "输出"),
                  os.path.join(BASE, "01a眼窝眼球", "_中间"),
                  os.path.join(BASE, "02QR拓扑"),
                  os.path.join(BASE, "03自动UV"),
                  os.path.join(BASE, "04纹理烘焙"),
                  os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")]'''),
 # 13) status 列表
 ('''        ("01 高模修复", "01高模修复与黏连检测/models/01_highpoly_repair.blend"),
        ("01a 眼窝", "01A眼窝与眼球/models/01_1_eye_socket.blend"),
        ("02 眼球(QR后摆入)", "01A眼窝与眼球/models/01_2_eyeball_placed.blend"),
        ("02 QR拓扑", "02QuadRemesher拓扑/02_qr_150k_socket.blend"),
        ("03 UV", "03自动UV/03_auto_uv.blend"),
        ("04 烘焙", "04纹理烘焙/04_bake.blend"),''',
  '''        ("01 高模修复", "01高模修复/输出/01_highpoly_repair.blend"),
        ("01a 眼窝", "01a眼窝眼球/输出/01_1_eye_socket.blend"),
        ("02 眼球(QR后摆入)", "01a眼窝眼球/输出/01_2_eyeball_placed.blend"),
        ("02 QR拓扑", "02QR拓扑/输出/02_qr_150k_socket.blend"),
        ("02 未补洞(QR)", "02QR拓扑/输出/02_qr_150k_未补洞_拓扑后.blend"),
        ("03 UV", "03自动UV/输出/03_auto_uv.blend"),
        ("04 烘焙", "04纹理烘焙/输出/04_bake.blend"),'''),
 ('        p = os.path.join(DELIVERY, rel)', '        p = os.path.join(BASE, rel)'),
]

hits = 0
for old, new in REPS:
    if old not in s:
        print(f"[❌未匹配] {old[:70]}", flush=True); continue
    s = s.replace(old, new); hits += 1

# 12) clean: 删除 ② 交付生成产物白名单块(从 GEN 注释到该 for 循环末)
import re
pat = re.compile(r"    # 交付里的\"生成产物\"白名单\(相对交付目录\)\n(?:.*\n)*?.*?print\(f\"  \{G\}✓ 清理 \{k\} \(输出/ \+ 交付生成物\)\{W\}\"\)\n", re.M)
m = pat.search(s)
if m:
    s = s[:m.start()] + s[m.end():]
    print("[✓] 已删除 clean 的 ②交付生成产物白名单块", flush=True)
else:
    print("[⚠] clean 白名单块未按正则匹配到, 需人工检查", flush=True)

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print(f"CONSOLE_DONE (替换 {hits}/{len(REPS)} 处)", flush=True)
# 残留
for i, ln in enumerate(s.splitlines(), 1):
    if "交付" in ln or "DELIVERY" in ln:
        print(f"  残留 L{i}: {ln.strip()[:90]}", flush=True)
