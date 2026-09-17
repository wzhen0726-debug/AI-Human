# -*- coding: utf-8 -*-
"""2026-09-17 全面归位: 删 交付/ 目录概念, 测试期产物按用户约定直接写各 stage 的 输出/.
本脚本: ① 搬家(交付/ → 工作区各stage) ② 重写独立脚本里的路径常量.
控制台.py 单独处理(另一步), 本脚本不碰它.
"""
import os, shutil, ast

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
DV = os.path.join(ROOT, "交付")
assert os.path.isdir(DV), "交付目录不存在?"

LOG = []

def mv(src_rel, dst_rel):
    s = os.path.join(DV, src_rel)
    d = os.path.join(ROOT, dst_rel)
    if not os.path.exists(s):
        LOG.append(f"[skip缺] {src_rel}")
        return
    os.makedirs(os.path.dirname(d.rstrip("\\/")), exist_ok=True)
    if os.path.isdir(d):
        # 合并目录内容
        n = 0
        for it in sorted(os.listdir(s)):
            if it == "__pycache__" or it.endswith(".blend1") or it.endswith(".pyc"):
                continue
            tgt = os.path.join(d, it)
            if os.path.exists(tgt):
                LOG.append(f"[已存在跳过] {dst_rel}/{it}")
                continue
            shutil.move(os.path.join(s, it), tgt); n += 1
        LOG.append(f"[合并] {src_rel} -> {dst_rel} ({n}项)")
    else:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.move(s, d)
        LOG.append(f"[移动] {src_rel} -> {dst_rel}")

# ============ ① 搬家 ============
mv("01高模修复与黏连检测/scripts", "01高模修复/scripts")
mv("01高模修复与黏连检测/models", "01高模修复/输出")
# 01a
mv("01A眼窝与眼球/scripts", "01a眼窝眼球/scripts")
mv("01A眼窝与眼球/models/01_1_eye_socket.blend", "01a眼窝眼球/输出/01_1_eye_socket.blend")
mv("01A眼窝与眼球/models/01_2_eyeball_placed.blend", "01a眼窝眼球/输出/01_2_eyeball_placed.blend")
mv("01A眼窝与眼球/models/01A_markers_eyelid.blend", "01a眼窝眼球/输出/01A_markers_eyelid.blend")
mv("01A眼窝与眼球/models/_中间/01_1_eye_socket_qr.blend", "01a眼窝眼球/_中间/01_1_eye_socket_qr.blend")
mv("01A眼窝与眼球/screenshots/3ddfa", "01a眼窝眼球/3ddfa")
mv("01A眼窝与眼球/screenshots", "01a眼窝眼球/screenshots")
# 脚本旧备份 -> 项目根/_备份/
for f in ("assign_socket_material.py.bak_20260909_160909", "socket_ops.py.bak_20260910_192655_碗面重构前"):
    s = os.path.join(DV, "01A眼窝与眼球/scripts/_备份", f)
    if os.path.exists(s):
        d = os.path.join(ROOT, "_备份", "脚本旧备份_20260917", f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.move(s, d); LOG.append(f"[备份归位] _备份/脚本旧备份_20260917/{f}")
# 02
mv("02QuadRemesher拓扑/scripts", "02QR拓扑/scripts")
mv("02QuadRemesher拓扑/02_qr_150k_socket.blend", "02QR拓扑/输出/02_qr_150k_socket.blend")
mv("02QuadRemesher拓扑/02_qr_150k_未补洞_拓扑后.blend", "02QR拓扑/输出/02_qr_150k_未补洞_拓扑后.blend")
mv("02QuadRemesher拓扑/02_qr_150k.fbx", "02QR拓扑/输出/02_qr_150k.fbx")
mv("02QuadRemesher拓扑/_中间", "02QR拓扑/_中间")
# 03/04
mv("03自动UV/scripts", "03自动UV/scripts")
mv("04纹理烘焙/scripts", "04纹理烘焙/scripts")
# 05
mv("05骨骼绑定/ARP新版测试_20260831", "05骨骼绑定/ARP新版测试_20260831")
mv("05骨骼绑定/_工作区_过程文件", "05骨骼绑定/_工作区_过程文件")
mv("05骨骼绑定/手动工具_不参与自动流程", "05骨骼绑定/手动工具_不参与自动流程")

print("\n".join(LOG), flush=True)
print("MOVES_DONE", flush=True)

# ============ ② 重写独立脚本的路径 ============
BASEQ = "E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"
EDIT = {  # 文件(新路径) -> [(old, new), ...]
 r"01a眼窝眼球\scripts\eye_socket_config.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"\nS01A = os.path.join(ROOT, "01a眼窝眼球")  # 2026-09-17 全面归位: 不再有 交付/ 目录, 产物写各stage的 输出/'),
   ('# 测试阶段产物位置(用户约定 2026-09-09: 测试期产物写各stage的 输出/, 交付/ 只在定稿后整理)',
    '# 产物位置(用户约定: 测试期产物写各stage的 输出/; 交付/ 只定稿后整理 — 2026-09-17 已删除交付目录概念)'),
   ('os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")',
    'os.path.join(ROOT, "01高模修复", "输出", "01_highpoly_repair.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")',
    'os.path.join(S01A, "输出", "01_1_eye_socket.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", ',
    'os.path.join(S01A, "3ddfa", '),
 ],
 r"01a眼窝眼球\scripts\assign_socket_material.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"\nS01A = os.path.join(ROOT, "01a眼窝眼球")'),
   ('# 测试阶段产物位置(用户约定 2026-09-09: 测试期产物写各stage的 输出/, 交付/ 只在定稿后整理)', ''),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")',
    'os.path.join(S01A, "输出", "01_1_eye_socket.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "_中间", "01_1_eye_socket_qr.blend")',
    'os.path.join(S01A, "_中间", "01_1_eye_socket_qr.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", ',
    'os.path.join(S01A, "3ddfa", '),
 ],
 r"01a眼窝眼球\scripts\eyeball_config.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"\nS01A = os.path.join(ROOT, "01a眼窝眼球")'),
   ('# 测试阶段产物位置(用户约定 2026-09-09: 测试期产物写各stage的 输出/, 交付/ 只在定稿后整理)', ''),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")',
    'os.path.join(S01A, "输出", "01_1_eye_socket.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")',
    'os.path.join(S01A, "输出", "01_2_eyeball_placed.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", ',
    'os.path.join(S01A, "3ddfa", '),
 ],
 r"01a眼窝眼球\scripts\mirror_markers.py": [
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")',
    'os.path.join(S01A, "输出", "01A_markers_eyelid.blend")'),
 ],
 r"01a眼窝眼球\scripts\place_eyelid_markers.py": [
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")',
    'os.path.join(S01A, "输出", "01A_markers_eyelid.blend")'),
 ],
 r"01a眼窝眼球\scripts\read_eyelid_markers.py": [
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")',
    'os.path.join(S01A, "输出", "01A_markers_eyelid.blend")'),
   ('os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", ',
    'os.path.join(S01A, "3ddfa", '),
 ],
 r"01a眼窝眼球\scripts\graze_angle_check.py": [
   ('os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json")',
    'os.path.join(D,"01a眼窝眼球","3ddfa","eyelid_contour_manual.json")'),
 ],
 r"01a眼窝眼球\scripts\eye002_config.py": [
   ('EYE_XZ_JSON = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\01A眼窝与眼球\\screenshots\\3ddfa\\eyelid_contour_manual.json"',
    'EYE_XZ_JSON = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\01a眼窝眼球\\3ddfa\\eyelid_contour_manual.json"'),
 ],
 r"02QR拓扑\scripts\02_qr_auto.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"'),
   ('# 2026-09-09 用户明确: 测试阶段产物权威位置是 02QR拓扑/输出/(GUI核验处), 不是交付/.',
    '# 2026-09-09 用户明确: 测试阶段产物权威位置是 02QR拓扑/输出/(GUI核验处). 2026-09-17 归位: 交付/ 已删.'),
   ('# 交付/ 是流程定稿后才整理的位置; 测试期所有QR产物直接写到 02QR拓扑/输出/.',
    '# 所有QR产物直接写到 02QR拓扑/输出/; 中间件写 02QR拓扑/_中间/.'),
   ('OUT_02 = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\02QuadRemesher拓扑"',
    'W_02 = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\02QR拓扑"\nOUT_02 = os.path.join(W_02, "输出")'),
   ('blend_path = os.path.join(r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\01A眼窝与眼球\\models\\_中间", "01_1_eye_socket_qr.blend")',
    'blend_path = os.path.join(r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\01a眼窝眼球\\_中间", "01_1_eye_socket_qr.blend")'),
   ('os.path.join(OUT_02, "_中间"', 'os.path.join(W_02, "_中间"'),
 ],
 r"02QR拓扑\scripts\02qr_socket_cup.py": [
   ('QR_BLEND = os.path.join(D, "交付", "02QuadRemesher拓扑", "_中间", "02_qr_150k.blend")',
    'QR_BLEND = os.path.join(D, "02QR拓扑", "_中间", "02_qr_150k.blend")'),
   ('EYE_BLEND = os.path.join(D, "交付", "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")',
    'EYE_BLEND = os.path.join(D, "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")'),
   ('OUT = os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k_socket.blend")',
    'OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")'),
   ('J = json.load(open(os.path.join(D, "交付", "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))',
    'J = json.load(open(os.path.join(D, "01a眼窝眼球", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))'),
 ],
 r"03自动UV\scripts\03_auto_uv.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"'),
   ('QR_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_socket.blend")',
    'QR_BLEND = os.path.join(ROOT, "02QR拓扑", "输出", "02_qr_150k_socket.blend")'),
   ('OUT_03 = os.path.join(DELIVERY, "03自动UV")', 'OUT_03 = os.path.join(ROOT, "03自动UV", "输出")'),
 ],
 r"04纹理烘焙\scripts\04_bake.py": [
   ('DELIVERY = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付"',
    'ROOT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端"'),
   ('UV_BLEND = os.path.join(DELIVERY, "03自动UV", "03_auto_uv.blend")',
    'UV_BLEND = os.path.join(ROOT, "03自动UV", "输出", "03_auto_uv.blend")'),
   ('HIGH_POLY = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")',
    'HIGH_POLY = os.path.join(ROOT, "01a眼窝眼球", "输出", "01_1_eye_socket.blend")'),
   ('FIXED_TEX = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_original_tex_fixed.png")',
    'FIXED_TEX = os.path.join(ROOT, "01高模修复", "输出", "01_original_tex_fixed.png")'),
   ('OUT_04 = os.path.join(DELIVERY, "04纹理烘焙")', 'OUT_04 = os.path.join(ROOT, "04纹理烘焙", "输出")'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\run_all.py": [
   ('BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定\\ARP新版测试_20260831"',
    'BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定\\ARP新版测试_20260831"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\step1_ai_markers.py": [
   ('BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定"',
    'BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定"'),
   ('BAKE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\04纹理烘焙\\04_bake.blend"',
    'BAKE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\04纹理烘焙\\输出\\04_bake.blend"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\step2_go_detect.py": [
   ('OUT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定\\ARP新版测试_20260831"',
    'OUT = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定\\ARP新版测试_20260831"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\step3_to_7_rig_and_walk.py": [
   ('BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定"',
    'BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\normalize_to_tpose.py": [
   ('W05 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")',
    'W05 = os.path.join(D, "05骨骼绑定", "ARP新版测试_20260831")'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\qa_rig.py": [
   ('r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定\\ARP新版测试_20260831\\03_骨骼绑定.blend"',
    'r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定\\ARP新版测试_20260831\\03_骨骼绑定.blend"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\qa_walk.py": [
   ('r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定\\ARP新版测试_20260831\\04_动作测试.blend"',
    'r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定\\ARP新版测试_20260831\\04_动作测试.blend"'),
 ],
 r"05骨骼绑定\ARP新版测试_20260831\scripts\retarget_mixamo.py": [
   ('BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\05骨骼绑定\\ARP新版测试_20260831"',
    'BASE = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\05骨骼绑定\\ARP新版测试_20260831"'),
 ],
 r"05骨骼绑定\手动工具_不参与自动流程\transplant_manual_markers.py": [
   ('W = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")',
    'W = os.path.join(D, "05骨骼绑定", "ARP新版测试_20260831")'),
 ],
}

ok_cnt = 0
for rel, reps in EDIT.items():
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print(f"[❌文件不存在] {rel}", flush=True); continue
    s = open(p, encoding="utf-8").read()
    for old, new in reps:
        if old not in s:
            print(f"[❌未匹配] {rel} :: {old[:60]}", flush=True); continue
        s = s.replace(old, new)
        ok_cnt += 1
    ast.parse(s)  # 语法自检
    open(p, "w", encoding="utf-8").write(s)
print(f"REWRITES_DONE (替换 {ok_cnt} 处)", flush=True)

# ============ ③ 残留检查 ============
import re
left = []
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ("_备份", ".git", "logs", "__pycache__")]
    if os.path.abspath(root).startswith(os.path.abspath(DV)):
        continue  # 交付自身(还没删)
    for f in files:
        if f.endswith((".py", ".sh")):
            fp = os.path.join(root, f)
            try:
                t = open(fp, encoding="utf-8").read()
            except Exception:
                continue
            if "交付" in t and "_fix_" not in f:
                left.append(os.path.relpath(fp, ROOT))
print("残留提及交付(排除logs/_fix_):", left[:20], flush=True)
print("REFACTOR_PART1_DONE", flush=True)
