"""修复: 归一化后重新蒙皮(修复关节撕裂), 重新生成03_骨骼绑定.blend
根因: normalize_rest改了骨骼朝向, 但蒙皮权重是按旧rest算的 → 关节处撕裂
方案: 在归一化骨架上重做自动权重(蒙皮按新rest重新计算)
输出: 03_骨骼绑定.blend (覆盖, 权重修复版)"""
import bpy, os
BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
RIG = os.path.join(BASE, "03_mixamo_rest.blend")
OUT = os.path.join(BASE, "03_骨骼绑定.blend")

bpy.ops.wm.open_mainfile(filepath=RIG)
arm = bpy.data.objects.get('MixamoSkeleton')
body = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('tripo'))
eyes = [o for o in bpy.data.objects if o.name.startswith('Eye002')]

print(f"骨架: {arm.name} {len(arm.data.bones)}骨")
print(f"身体: {body.name} {len(body.data.vertices)}顶点")
print(f"眼球: {[o.name for o in eyes]}")

# 清旧蒙皮权重 + 重算
n_vg_before = len(body.vertex_groups)
for vg in list(body.vertex_groups):
    body.vertex_groups.remove(vg)
print(f"清旧顶点组: {n_vg_before}个")

bpy.context.view_layer.objects.active = arm
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); arm.select_set(True)
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print(f"重蒙皮后: {len(body.vertex_groups)}顶点组, 修改器={[m.type for m in body.modifiers]}")

# 眼球重新蒙皮到Head(清旧再绑)
for eye in eyes:
    for vg in list(eye.vertex_groups):
        eye.vertex_groups.remove(vg)
    for m in list(eye.modifiers):
        if m.type == 'ARMATURE': eye.modifiers.remove(m)
    vg = eye.vertex_groups.new(name='mixamorig:Head')
    vg.add(list(range(len(eye.data.vertices))), 1.0, 'REPLACE')
    mod = eye.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    mod.use_deform_preserve_volume = True
    print(f"  {eye.name} 重蒙皮到Head")

# 保存覆盖03
bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"已保存(覆盖): {OUT}")
print("FIX_WEIGHT_DONE")
