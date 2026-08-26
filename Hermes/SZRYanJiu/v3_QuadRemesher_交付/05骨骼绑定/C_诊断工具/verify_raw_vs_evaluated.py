"""根因验证: 13个标记点的原始坐标 vs 约束求值后坐标."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
scn = bpy.context.scene
scn.frame_set(1)
scn.update_tag()
bpy.context.view_layer.update()

print(f"{'标记点':<28} {'原始location':>26} {'求值后matrix_world':>28} {'一致?'}")
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if not o.name.startswith('LM_'):
        continue
    raw = o.location
    eva = o.matrix_world.translation
    same = (abs(raw.x-eva.x) + abs(raw.y-eva.y) + abs(raw.z-eva.z)) < 0.001
    mark = "  YES" if same else "  *** NO ***"
    ncons = len(o.constraints)
    print(f"{o.name:<28} ({raw.x:+.3f},{raw.y:+.3f},{raw.z:+.3f}) ({eva.x:+.3f},{eva.y:+.3f},{eva.z:+.3f}){mark} 约束x{ncons}")
print("ROOT_CAUSE_VERIFY_DONE")
