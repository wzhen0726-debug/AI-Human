"""对照: Mixamo T-Pose参考骨架 vs 我们骨架, 每根关键骨骼的局部Z/Y轴在世界系的方向.
→ 找出roll差异. Mixamo骨骼约定: Y=骨骼延伸方向, Z=弯曲参考轴."""
import bpy, os, glob
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "logs", "roll_compare.txt")
out = []

def dump(rig, label, names):
    out.append(f"===== {label} =====")
    for bn in names:
        b = rig.data.bones.get(bn)
        if not b: continue
        M = rig.matrix_world @ b.matrix_local
        y = (M.to_3x3() @ Vector((0,1,0))).normalized()
        z = (M.to_3x3() @ Vector((0,0,1))).normalized()
        x = (M.to_3x3() @ Vector((1,0,0))).normalized()
        out.append(f"{bn}:")
        out.append(f"  Y(延伸)={tuple(round(c,2) for c in y)}")
        out.append(f"  Z(弯曲参考)={tuple(round(c,2) for c in z)}")
        out.append(f"  X={tuple(round(c,2) for c in x)}")

# Mixamo T-pose参考
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\T-Pose.fbx")
mrig = next((o for o in bpy.data.objects if o.type=='ARMATURE'), None)
dump(mrig, "Mixamo T-Pose", ['mixamorig:LeftArm','mixamorig:LeftForeArm','mixamorig:LeftHand',
    'mixamorig:LeftUpLeg','mixamorig:LeftLeg','mixamorig:LeftFoot','mixamorig:LeftToeBase',
    'mixamorig:LeftHandIndex1','mixamorig:LeftHandThumb1'])

# 我们
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend"))
urig = next((o for o in bpy.data.objects if o.type=='ARMATURE'), None)
dump(urig, "我们的手写版", ['mixamorig:LeftArm','mixamorig:LeftForeArm','mixamorig:LeftHand',
    'mixamorig:LeftUpLeg','mixamorig:LeftLeg','mixamorig:LeftFoot','mixamorig:LeftToeBase',
    'mixamorig:LeftHandIndex1','mixamorig:LeftHandThumb1'])

out.append("DONE")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))