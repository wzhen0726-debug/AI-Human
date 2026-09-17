"""演示版_终端控制端 → v3_QuadRemesher_交付: 脚本/数据 同步 (2026-09-17)
演示版为当前权威实现; 交付版补齐所有更新脚本与新增脚本。
"""
import os, shutil, filecmp

BASE = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu"
DEMO = os.path.join(BASE, "演示版_终端控制端")
DELV = os.path.join(BASE, "v3_QuadRemesher_交付")

# (源目录, 目标目录, 说明, 是否复制非py文件)
JOBS = [
    (f"{DEMO}/01高模修复/scripts", f"{DELV}/01高模修复与黏连检测/scripts", "01 高模修复", False),
    (f"{DEMO}/01a眼窝眼球/scripts", f"{DELV}/01A眼窝与眼球/scripts", "01a 眼窝眼球 脚本", False),
    (f"{DEMO}/01a眼窝眼球/3ddfa", f"{DELV}/01A眼窝与眼球/3ddfa", "01a 手调数据(3ddfa三json)", False),
    (f"{DEMO}/02QR拓扑/scripts", f"{DELV}/02QuadRemesher拓扑/scripts", "02 拓扑脚本", False),
    (f"{DEMO}/03自动UV/scripts", f"{DELV}/03自动UV/scripts", "03 UV脚本", False),
    (f"{DEMO}/04纹理烘焙/scripts", f"{DELV}/04纹理烘焙/scripts", "04 烘焙脚本", False),
    (f"{DEMO}/05骨骼绑定/ARP新版测试_20260831/scripts",
     f"{DELV}/05骨骼绑定/ARP新版测试_20260831/scripts", "05 绑定脚本", False),
    (f"{DEMO}/06GLB导出/scripts", f"{DELV}/06GLB导出/scripts", "06 GLB脚本(新建)", False),
]
SINGLE = [
    (f"{DEMO}/05骨骼绑定/ARP新版测试_20260831/点位指南.md",
     f"{DELV}/05骨骼绑定/ARP新版测试_20260831/点位指南.md", "05 点位指南"),
    (f"{DEMO}/05骨骼绑定/手动工具_不参与自动流程/transplant_manual_markers.py",
     f"{DELV}/05骨骼绑定/手动工具_不参与自动流程/transplant_manual_markers.py", "05 手动工具"),
]

new_cnt = upd_cnt = same_cnt = miss = 0
for src, dst, label, _ in JOBS:
    if not os.path.isdir(src):
        print(f"  ✗ 源不存在: {src}"); miss += 1; continue
    os.makedirs(dst, exist_ok=True)
    n_new = n_upd = n_same = 0
    for f in sorted(os.listdir(src)):
        sp = os.path.join(src, f)
        if not os.path.isfile(sp) or not f.endswith((".py", ".json")):
            continue
        dp = os.path.join(dst, f)
        if os.path.exists(dp):
            if filecmp.cmp(sp, dp, shallow=False):
                n_same += 1; continue
            shutil.copy2(sp, dp); n_upd += 1
        else:
            shutil.copy2(sp, dp); n_new += 1
    new_cnt += n_new; upd_cnt += n_upd; same_cnt += n_same
    print(f"  {label}: 新增{n_new} 更新{n_upd} 相同{n_same}")

for src, dst, label in SINGLE:
    if not os.path.exists(src):
        print(f"  ✗ 源不存在: {label}"); miss += 1; continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        print(f"  {label}: 相同"); same_cnt += 1; continue
    exists = os.path.exists(dst)
    shutil.copy2(src, dst)
    upd_cnt += 1 if exists else 0; new_cnt += 0 if exists else 1
    print(f"  {label}: {'更新' if exists else '新增'}")

print(f"\n小计: 新增{new_cnt} 更新{upd_cnt} 相同{same_cnt} 缺失{miss}")
