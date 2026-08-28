"""两版绑定一键执行 (用户打点完成后运行)
流程:
  手写版: 镜像L侧 → 从标记生成骨骼+权重+Mixamo命名 → GLB
  ARP版: 后台Smart绑定 → Mixamo 65骨骼 → 清约束 → GLB
  验证: 两版骨骼数/权重覆盖/行走动画
用法: blender -b --python run_two_versions.py
"""
import bpy, os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(BASE, "A_半自动打点")
B = os.path.join(BASE, "B_骨骼绑定")
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"

def run_script(label, script):
    print(f"\n{'='*50}", flush=True)
    print(f"[{label}] {script}", flush=True)
    r = subprocess.run([BLENDER, "-b", "--python", script],
                       capture_output=True, text=True, timeout=1800)
    # 只打印关键行
    for line in r.stdout.splitlines():
        if any(k in line for k in ("DONE", "骨骼", "权重", "保存", "ERROR", "成功", "失败", "前缀", "帧")):
            print("   ", line.strip(), flush=True)
    if r.returncode != 0:
        print(f"   !! 退出码 {r.returncode}", flush=True)
        for line in r.stderr.splitlines()[-5:]:
            print("   ", line.strip(), flush=True)
    return r.returncode

print("=== 两版绑定流水线 ===", flush=True)

# 0. 校验用户已打点(标记位置是否已从默认值调整)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(A, "06_rig_markers.blend"))
markers = [o for o in bpy.data.objects if o.type == 'EMPTY']
print(f"标记点数: {len(markers)}", flush=True)
for o in sorted(markers, key=lambda x: x.name):
    print(f"   {o.name}: ({o.location.x:+.3f},{o.location.y:+.3f},{o.location.z:+.3f})", flush=True)

# 1. 手写版: 镜像 + 绑定
run_script("手写版-镜像", os.path.join(A, "mirror_rig_markers.py"))
run_script("手写版-绑定", os.path.join(B, "rig_from_markers.py"))

# 2. ARP版
run_script("ARP-绑定", os.path.join(B, "arp_rig.py"))
run_script("ARP-Mixamo命名", os.path.join(B, "arp_to_mixamo.py"))
run_script("ARP-补末端骨", os.path.join(B, "fill_mixamo_ends.py"))
run_script("ARP-加前缀", os.path.join(B, "add_mixamo_prefix.py"))

print("\n=== 流水线完成 ===", flush=True)
print("TWO_VERSIONS_DONE", flush=True)
