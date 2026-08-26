"""修复: L侧标记点改为驱动器实时镜像(2026-08-26根因修复)
根因: 之前镜像脚本生成静态副本, 与R侧断开 → "两套点"+"不能同步镜像"
修复: 每个L点location由驱动器实时从对应R点计算 (x取反, y/z跟随),
      并锁定L点不可选中, 用户只需操作R侧."""
import bpy

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

r_objs = {o.name: o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.endswith('_R')}
l_objs = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.endswith('_L')]

def find_pair(L):
    rname = L.name.replace("左", "右")
    rname = rname[:-2] + "_R" if rname.endswith("_L") else rname + "_R"
    return r_objs.get(rname)

fixed = []
for L in l_objs:
    R = find_pair(L)
    if not R:
        print(f"  警告: {L.name} 找不到R侧配对")
        continue
    if L.animation_data:
        L.animation_data_clear()
    for i, (axis, sign) in enumerate([("X", -1), ("Y", 1), ("Z", 1)]):
        fcurve = L.driver_add("location", i)
        drv = fcurve.driver
        drv.type = 'SCRIPTED'
        drv.expression = "-val" if sign < 0 else "val"
        var = drv.variables.new()
        var.name = "val"
        var.type = 'TRANSFORMS'
        tgt = var.targets[0]
        tgt.id = R
        tgt.transform_type = 'LOC_' + axis
        tgt.transform_space = 'LOCAL_SPACE'
    L.hide_select = True      # 锁定不可选中, 防误碰(只操作R侧)
    fixed.append((L.name, R.name))
    print(f"  {L.name} ←实时镜像← {R.name}")

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"\n共{len(fixed)}个L点改为实时镜像, 已保存")
print("LIVE_MIRROR_DONE")
