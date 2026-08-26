"""验证手写版骨骼位置与用户打点的匹配."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\B_骨骼绑定\06_rig_final.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if not arm:
    print("ERROR: 无骨架")
    raise SystemExit(1)

print(f"骨架: {arm.name}, 骨骼数: {len(arm.data.bones)}")
for b in arm.data.bones:
    h = arm.matrix_world @ b.head_local
    t = arm.matrix_world @ b.tail_local
    print(f"  {b.name}: head({h.x:.3f},{h.y:.3f},{h.z:.3f}) tail({t.x:.3f},{t.y:.3f},{t.z:.3f})")
print("VERIFY_HANDWRITE_DONE")
