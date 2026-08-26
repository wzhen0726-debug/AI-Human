"""检查打点模板每个标记点的约束栈."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== 标记点约束栈 ===")
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if not o.name.startswith("LM_"):
        continue
    print(f"{o.name}:")
    for c in o.constraints:
        extra = ""
        if c.type == 'SHRINKWRAP':
            extra = f" mode={c.shrinkwrap_type} dist={c.distance:.3f}"
        elif c.type == 'LIMIT_LOCATION':
            extra = f" X锁={c.use_min_x}/{c.use_max_x} x范围=[{c.min_x:.3f},{c.max_x:.3f}]"
        print(f"    - {c.type}{extra}")
print("CHECK_CONSTRAINTS_DONE")
