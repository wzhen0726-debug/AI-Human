"""检查打点模板文件的标记点现状: 数量/命名/位置/重复."""
import bpy, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(BASE, "05骨骼绑定", "A_半自动打点", "06_rig_markers.blend")

bpy.ops.wm.open_mainfile(filepath=TEMPLATE)
print("\n=== 所有EMPTY对象(标记点) ===")
empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
print(f"总数: {len(empties)}")
for o in empties:
    l = o.location
    print(f"  {o.name:32s} pos=({l.x:+.3f},{l.y:+.3f},{l.z:+.3f})")

print("\n=== 集合结构 ===")
for c in bpy.data.collections:
    print(f"  集合 {c.name}: {len(c.objects)} 个对象")
    for o in c.objects:
        if o.type == 'EMPTY':
            print(f"    - {o.name}")

print("\n=== 重复检查 ===")
# 检查同位置重复点
from collections import defaultdict
pos_map = defaultdict(list)
for o in empties:
    key = (round(o.location.x,2), round(o.location.y,2), round(o.location.z,2))
    pos_map[key].append(o.name)
dups = {k:v for k,v in pos_map.items() if len(v)>1}
if dups:
    print(f"发现 {len(dups)} 处同位置重复:")
    for k, v in dups.items():
        print(f"  位置{k}: {v}")
else:
    print("无同位置重复")
print("\nDUP_CHECK_DONE")
