"""检查06_rig_markers.blend模板的真实内容: 集合/标记点/约束/命名."""
import bpy, os

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== 集合 ===")
for c in bpy.data.collections:
    print(f"  {c.name}: {len(c.objects)} 对象")

print("\n=== 所有标记点(按集合) ===")
for c in bpy.data.collections:
    for o in c.objects:
        cons = [cn.type for cn in o.constraints] if hasattr(o, 'constraints') else []
        print(f"  [{c.name}] {o.name}  pos=({o.location[0]:.3f},{o.location[1]:.3f},{o.location[2]:.3f})  show_in_front={o.show_in_front}  约束={cons}")

print("\n=== 网格/其他对象 ===")
for o in bpy.data.objects:
    if o.type == 'MESH':
        print(f"  MESH {o.name}: {len(o.data.polygons)}面")

print("CHECK_DONE")
