# -*- coding: utf-8 -*-
"""终验A方案: 全链所有产物无bevel权重/无BEVEL修改器 + 05骨架结构与动画完好."""
import bpy, os
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
FILES = [
    (os.path.join(D, "交付", "02QuadRemesher拓扑", "02_qr_150k.blend"), "02_QR"),
    (os.path.join(D, "交付", "03自动UV", "03_auto_uv.blend"), "03_UV"),
    (os.path.join(D, "交付", "04纹理烘焙", "04_bake.blend"), "04_烘焙"),
    (os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "03_骨骼绑定.blend"), "05_绑定"),
    (os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "04_动作测试.blend"), "05_动作"),
    (os.path.join(D, "02QR拓扑", "输出", "02_qr_150k.blend"), "输出_02"),
    (os.path.join(D, "03自动UV", "输出", "03_auto_uv.blend"), "输出_03"),
    (os.path.join(D, "04纹理烘焙", "输出", "04_bake.blend"), "输出_04"),
    (os.path.join(D, "05骨骼绑定", "输出", "03_骨骼绑定.blend"), "输出_05绑定"),
    (os.path.join(D, "05骨骼绑定", "输出", "04_动作测试.blend"), "输出_05动作"),
]
fails = []
for path, tag in FILES:
    if not os.path.exists(path):
        fails.append(f"[{tag}] 文件不存在: {path}")
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    issues = []
    for o in bpy.data.objects:
        if o.type != 'MESH': continue
        for an in ("bevel_weight_edge", "bevel_weight_vert", "crease_edge", "crease_vert"):
            if o.data.attributes.get(an) is not None:
                issues.append(f"{o.name[:24]}带{an}")
        for m in o.modifiers:
            if m.type == 'BEVEL':
                issues.append(f"{o.name[:24]}挂BEVEL修改器")
    # 05专项检查
    if tag.startswith("05"):
        arm = next((o for o in bpy.data.objects if o.type=='ARMATURE'), None)
        if arm:
            nc = sum(1 for b in arm.data.bones if b.use_connect)
            if nc < 41: issues.append(f"连接骨仅{nc}/55")
            if tag == "05_动作":
                acts = [a.name for a in bpy.data.actions]
                if not {'Standard Walk','Running','Jump'} <= set(acts): issues.append(f"动作缺失:{acts}")
        else:
            issues.append("无骨架!")
    print(f"[{tag}] {'PASS' if not issues else 'FAIL: ' + '; '.join(issues)}")
    fails.extend([f"[{tag}] {i}" for i in issues])
print("\nFINAL: " + ("ALL PASS" if not fails else "FAILS=" + " | ".join(fails)))
