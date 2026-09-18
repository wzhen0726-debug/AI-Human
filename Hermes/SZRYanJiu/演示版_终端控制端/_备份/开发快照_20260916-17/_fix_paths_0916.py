# -*- coding: utf-8 -*-
"""统一改造 v2 (精确匹配实际行): 交付=正典; 中间件→_中间/"""
import os
D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"

def edit(rel, pairs, must=True):
    p = os.path.join(D, rel)
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1); print(f"  OK {rel}: {old[:60]}...")
        elif must:
            print(f"  FAIL {rel}: {old[:60]}..."); raise SystemExit(1)
        else:
            print(f"  SKIP {rel}: {old[:60]}...")
    open(p, "w", encoding="utf-8").write(s)
    import ast; ast.parse(s)

S1 = "交付/01A眼窝与眼球/scripts/"
# 1) 01A 正典输出 → 交付models
edit(S1+"eye_socket_config.py", [(
 'OUT_BLEND = os.environ.get("EYE_OUT_BLEND") or os.path.join(WORK, "01_1_eye_socket.blend")',
 'OUT_BLEND = os.environ.get("EYE_OUT_BLEND") or os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")')])
edit(S1+"eyeball_config.py", [(
 'OUT_BLEND = os.path.join(WORK, "01_2_eyeball_placed.blend")',
 'OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")')])
# 2) _qr 中间件
edit(S1+"assign_socket_material.py", [(
 'OUT = os.path.join(WORK, "01_1_eye_socket_qr.blend")',
 'OUT = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "_中间", "01_1_eye_socket_qr.blend")')])

S2 = "交付/02QuadRemesher拓扑/scripts/"
# 3) 02 正典 → 交付; 中间件 → _中间; 输入指向 01A 的 _中间
edit(S2+"02_qr_auto.py", [
 ('OUT_02 = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\02QR拓扑\\输出"',
  'OUT_02 = r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\02QuadRemesher拓扑"'),
 ('hi_check = os.path.join(OUT_02, "02QR输入_眼窝材质分区_高模.blend")',
  'hi_check = os.path.join(OUT_02, "_中间", "02QR输入_眼窝材质分区_高模.blend")'),
 ('check_blend = os.path.join(OUT_02, "02_qr_150k_材质分区检查.blend")',
  'check_blend = os.path.join(OUT_02, "_中间", "02_qr_150k_材质分区检查.blend")'),
 ('blend_path = os.path.join(WORK_01A, "01_1_eye_socket_qr.blend")',
  'blend_path = os.path.join(r"E:\\WangZhen_Project\\AI\\ShuZiRen\\Hermes\\SZRYanJiu\\演示版_终端控制端\\交付\\01A眼窝与眼球\\models\\_中间", "01_1_eye_socket_qr.blend")'),
 ('output_blend = os.path.join(OUT_02, "02_qr_150k.blend")',
  'output_blend = os.path.join(OUT_02, "_中间", "02_qr_150k.blend")'),
])
# 4) 碗脚本: 读中间件, 输出正典交付, 眼球读交付
edit(S2+"02qr_socket_cup.py", [
 ('QR_BLEND = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k.blend")',
  'QR_BLEND = os.path.join(D, "交付", "02QuadRemesher拓扑", "_中间", "02_qr_150k.blend")'),
 ('EYE_BLEND = os.path.join(D, "01a眼窝眼球", "输出", "01_2_eyeball_placed.blend")',
  'EYE_BLEND = os.path.join(D, "交付", "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")'),
 ('OUT = os.path.join(D, "02QR拓扑", "输出", "02_qr_150k_socket.blend")',
  'OUT = os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k_socket.blend")'),
])
# 5) 03 读交付正典(带碗)
edit("交付/03自动UV/scripts/03_auto_uv.py", [
 ('QR_BLEND = os.path.join(PROJECT_ROOT, "02QR拓扑", "输出", "02_qr_150k_socket.blend")  # 2026-09-16 改: 读活的02产物(带碗)',
  'QR_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_socket.blend")'),
 ('OUT_03 = os.path.join(PROJECT_ROOT, "03自动UV", "输出")  # 2026-09-16 改: OUT不得指交付',
  'OUT_03 = os.path.join(DELIVERY, "03自动UV")'),
], must=False)
edit("交付/04纹理烘焙/scripts/04_bake.py", [
 ('UV_BLEND = os.path.join(PROJECT_ROOT, "03自动UV", "输出", "03_auto_uv.blend")  # 2026-09-16 改: 读活的03产物',
  'UV_BLEND = os.path.join(DELIVERY, "03自动UV", "03_auto_uv.blend")'),
 ('HIGH_POLY = os.path.join(PROJECT_ROOT, "01a眼窝眼球", "输出", "01_1_eye_socket.blend")  # 2026-09-16 改: 用活的高模',
  'HIGH_POLY = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")'),
 ('OUT_04 = os.path.join(PROJECT_ROOT, "04纹理烘焙", "输出")  # 2026-09-16 改: OUT不得指交付',
  'OUT_04 = os.path.join(DELIVERY, "04纹理烘焙")'),
], must=False)
print("ALL_OK")
