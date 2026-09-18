# -*- coding: utf-8 -*-
"""控制台.py 改造: clean递归+清交付产物; 02接入碗工序; 状态口径更新"""
import os
D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
p = os.path.join(D, "控制台.py")
s = open(p, encoding="utf-8").read()

# ---------- 1) clean_output 整体替换 ----------
old_clean = '''def clean_output(target=None):
    """清理输出文件夹. target=None/单环节/all"""
    targets = {
        "01": os.path.join(BASE, "01高模修复", "输出"),
        "01a": os.path.join(BASE, "01a眼窝眼球", "输出"),
        "02": os.path.join(BASE, "02QR拓扑", "输出"),
        "03": os.path.join(BASE, "03自动UV", "输出"),
        "04": os.path.join(BASE, "04纹理烘焙", "输出"),
        "05": os.path.join(BASE, "05骨骼绑定", "输出"),
    }
    if target is None or target == "all":
        to_clean = list(targets.items())
    elif target in targets:
        to_clean = [(target, targets[target])]
    else:
        print(f"{R}✗ 未知目标: {target} (可用: 01/01a/02/03/04/05/all){W}"); return
    n = 0
    for k, d in to_clean:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    os.remove(fp); n += 1
            print(f"  {G}✓ 清理 {k}/输出{W}")
        else:
            print(f"  {D}○ {k}/输出 已空{W}")
    print(f"\\n{G}★ 清理完成, 共删除 {n} 个文件{W}")
    show_hint()'''

new_clean = '''def clean_output(target=None):
    """清理输出文件夹(递归) + 交付里的生成产物. target=None/单环节/all
    2026-09-16 修复: ①原版只删文件不删文件夹(screenshots残留) → 改递归
                    ②交付里的生成产物也一并清理(否则status一直显示已生成, 且下游读到旧产物)
    绝不删除: 脚本 / 手调文件(01A_markers_eyelid.blend/手调json/手调点位备份) / 原始文件 / _备份"""
    targets = {
        "01": os.path.join(BASE, "01高模修复", "输出"),
        "01a": os.path.join(BASE, "01a眼窝眼球", "输出"),
        "02": os.path.join(BASE, "02QR拓扑", "输出"),
        "03": os.path.join(BASE, "03自动UV", "输出"),
        "04": os.path.join(BASE, "04纹理烘焙", "输出"),
        "05": os.path.join(BASE, "05骨骼绑定", "输出"),
    }
    # 交付里的"生成产物"白名单(相对交付目录)
    gen_delivery = {
        "01": ["01高模修复与黏连检测/models/01_highpoly_repair.blend"],
        "01a": ["01A眼窝与眼球/models/01_1_eye_socket.blend",
                "01A眼窝与眼球/models/01_2_eyeball_placed.blend",
                "01A眼窝与眼球/models/_中间/01_1_eye_socket_qr.blend"],
        "02": ["02QuadRemesher拓扑/02_qr_150k_socket.blend",
               "02QuadRemesher拓扑/02_qr_150k.fbx",
               "02QuadRemesher拓扑/_中间/02_qr_150k.blend",
               "02QuadRemesher拓扑/_中间/02QR输入_眼窝材质分区_高模.blend",
               "02QuadRemesher拓扑/_中间/02_qr_150k_材质分区检查.blend"],
        "03": ["03自动UV/03_auto_uv.blend"],
        "04": ["04纹理烘焙/04_bake.blend", "04纹理烘焙/04_diffuse_4k.png",
               "04纹理烘焙/04_normal_4k.png", "04纹理烘焙/05_for_mixamo.fbx"],
        "05": ["05骨骼绑定/ARP新版测试_20260831/01_AI打点.blend",
               "05骨骼绑定/ARP新版测试_20260831/02_go_detect骨架.blend",
               "05骨骼绑定/ARP新版测试_20260831/03_骨骼绑定.blend",
               "05骨骼绑定/ARP新版测试_20260831/03B_骨骼标准化.blend",
               "05骨骼绑定/ARP新版测试_20260831/04_动作测试.blend"],
    }
    if target is None or target == "all":
        to_clean = list(targets.items())
    elif target in targets:
        to_clean = [(target, targets[target])]
    else:
        print(f"{R}✗ 未知目标: {target} (可用: 01/01a/02/03/04/05/all){W}"); return
    n = 0
    for k, d in to_clean:
        # ① 工作输出: 递归清空
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                try:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp); n += 1
                    else:
                        os.remove(fp); n += 1
                except Exception as e:
                    print(f"  {D}○ 跳过 {fp}: {e}{W}")
        # ② 交付生成产物: 白名单逐个删
        for rel in gen_delivery.get(k, []):
            fp = os.path.join(DELIVERY, rel)
            if os.path.exists(fp):
                try: os.remove(fp); n += 1
                except Exception: pass
        print(f"  {G}✓ 清理 {k} (输出/ + 交付生成物){W}")
    # 顺手清空目录壳
    for k, d in to_clean:
        pass
    print(f"\\n{G}★ 清理完成, 共删除 {n} 项{W}")
    show_hint()'''

assert old_clean in s, "clean块未匹配"
s = s.replace(old_clean, new_clean, 1)

# ---------- 2) step_02: 接入碗工序 + 正典改socket版 ----------
old2 = '''    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02_qr_auto.py"),
                       "02_QR", "QuadRemesher 自动拓扑(目标14万quad)"):
        summary("环节 02", False, t0, []); return False
    # (2026-09-08 A方案: rim倒角步骤已删除 — QR无rim边环, 倒角只落在眼周碎边上(用户实测发现), 无锐化效果)
    qr = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")'''
new2 = '''    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02_qr_auto.py"),
                       "02_QR", "QuadRemesher 自动拓扑(目标15万quad)"):
        summary("环节 02", False, t0, []); return False
    # 2026-09-16 新增: 眼窝碗重建(按眼球反推+打平+极点收口) — 正典产物=带碗版
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02qr_socket_cup.py"),
                       "02_碗", "眼窝碗重建(按眼球几何, 非穿透)", done_mark="SAVED:"):
        summary("环节 02", False, t0, []); return False
    qr = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_socket.blend")'''
assert old2 in s, "step_02块未匹配"
s = s.replace(old2, new2, 1)

# ---------- 3) step_03 输入检查 → socket版 ----------
old3 = 'if not check("02QuadRemesher拓扑/02_qr_150k.blend"):'
new3 = 'if not check("02QuadRemesher拓扑/02_qr_150k_socket.blend"):'
assert old3 in s, "step_03检查未匹配"
s = s.replace(old3, new3, 1)

# ---------- 4) status 02条目 → socket版 ----------
old4 = '("02 QR拓扑", "02QuadRemesher拓扑/02_qr_150k.blend"),'
new4 = '("02 QR拓扑", "02QuadRemesher拓扑/02_qr_150k_socket.blend"),'
assert old4 in s, "status未匹配"
s = s.replace(old4, new4, 1)

open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(s)
print("控制台.py 改造完成 ✓")
