"""验证模板约束: 每个标记点是否都有Shrinkwrap吸附."""
import bpy, os

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

ok = True
for cname in ["LM_M", "LM_R"]:
    c = bpy.data.collections.get(cname)
    for o in c.objects:
        sw = [cst for cst in o.constraints if cst.type == 'SHRINKWRAP']
        if sw:
            print(f"  [OK] {o.name}: Shrinkwrap→{sw[0].target.name}, 类型={sw[0].shrinkwrap_type}")
        else:
            ok = False
            print(f"  [缺] {o.name}: 无Shrinkwrap!")

print(f"\n验证{'通过' if ok else '失败'}: 所有标记点{'都有' if ok else '未全部有'}Shrinkwrap吸附")
print("VERIFY_DONE")
