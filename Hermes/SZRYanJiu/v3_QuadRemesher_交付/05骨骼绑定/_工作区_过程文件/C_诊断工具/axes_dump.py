"""精确对照: Mixamo T-Pose骨架的骨骼局部轴(armature空间, .z_axis) — pose旋转就在这个空间求值.
我们的骨架armature对象=identity, 其armature空间=世界空间.
映射: 他们的(a,b,c)在(左=+X,上=+Y,前=+Z)基下 → 我们 = a·(+X)+b·(+Z)+c·(-Y) = (a, -c, b)."""
import bpy, os
from mathutils import Vector

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "logs", "axes_armature_space.txt")
out = []

NAMES = ['LeftArm','LeftForeArm','LeftHand','LeftHandIndex1','LeftHandThumb1',
         'LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase','RightArm','RightUpLeg','RightFoot']

def map_theirs_to_ours(v):
    """他们armature空间向量 → 我们armature空间(左+X,上+Z,前-Y)"""
    return Vector((v.x, -v.z, v.y))

# Mixamo T-Pose
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\T-Pose.fbx")
mrig = next((o for o in bpy.data.objects if o.type=='ARMATURE'), None)
out.append(f"Mixamo骨架对象旋转: {tuple(mrig.rotation_euler)} 缩放:{tuple(mrig.scale)}")

# 验证朝向: 脚趾方向(armature空间)
lt = mrig.data.bones.get('mixamorig:LeftToeBase')
if lt:
    d = (lt.tail_local - lt.head_local).normalized()
    out.append(f"LeftToe延伸(armature空间): ({d.x:.2f},{d.y:.2f},{d.z:.2f}) → 确认面朝+Z")

out.append("")
out.append("骨骼 | 他们Z轴(armature) | 映射到我们空间的目标Z | 他们X轴(armature)")
for n in NAMES:
    b = mrig.data.bones.get(f"mixamorig:{n}")
    if not b: continue
    z = b.z_axis.normalized()
    x = b.x_axis.normalized()
    tz = map_theirs_to_ours(z)
    out.append(f"{n}: Z=({z.x:.2f},{z.y:.2f},{z.z:.2f}) → 目标=({tz.x:.2f},{tz.y:.2f},{tz.z:.2f}) | X=({x.x:.2f},{x.y:.2f},{x.z:.2f})")

out.append("DONE")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))