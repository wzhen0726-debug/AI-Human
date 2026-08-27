"""诊断: Mixamo参考骨架变换进我们世界系后, 逐骨对比方向.
我们的模型: Z-up, 面朝-Y, 单位m. Mixamo FBX: Y-up, 面朝+Z, 单位cm, obj_rot=(π/2,0,0).
变换: mixamo世界系点(x,y,z)_cm → 我们(x/100, -z/100, y/100).
旋转基映射: mx=(1,0,0)→(1,0,0); my=(0,1,0)→(0,0,1); mz=(0,0,1)→(0,-1,0).
输出每骨: Y延伸方向差° / Z(roll)方向差° + 我们的实测值."""
import bpy, os, glob, json, math
from mathutils import Vector, Matrix

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "logs", "mixamo_mapped.txt")
FBX_GLOB = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\*.fbx"

# Mixamo骨架世界矩阵 → 我们世界系
P = Matrix(((0.01, 0, 0, 0), (0, 0, -0.01, 0), (0, 0.01, 0, 0), (0, 0, 0, 1)))
def map_vec(v):
    return Vector((v.x, -v.z, v.y))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend"))
our_rig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and not o.name.startswith("Alpha") and o.name != "Armature":
        our_rig = o
        break
our = {b.name: our_rig.matrix_world @ b.matrix_local for b in our_rig.data.bones}
our_len = {b.name: b.length for b in our_rig.data.bones}

bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = None
for f in glob.glob(FBX_GLOB):
    if "walk" in f.lower():
        fbx = f
        break
if fbx is None:
    fbx = glob.glob(FBX_GLOB)[0]
bpy.ops.import_scene.fbx(filepath=fbx)
mrig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        if mrig is None or len(o.data.bones) > len(mrig.data.bones):
            mrig = o

lines = [f"FBX={os.path.basename(fbx)} obj_rot={list(mrig.rotation_euler)}"]
lines.append(f"{'骨骼':<28} {'Y差°':>7} {'Z差°':>7} {'长度比':>7}  我们z / mixamo映射z")
common = sorted(set(our) & {b.name for b in mrig.data.bones})
big = []
for n in common:
    mb = mrig.data.bones[n]
    mm = mrig.matrix_world @ mb.matrix_local
    # mixamo轴 → 我们世界系
    my_m = map_vec(mm.to_quaternion() @ Vector((0, 1, 0))).normalized()
    mz_m = map_vec(mm.to_quaternion() @ Vector((0, 0, 1))).normalized()
    mo = our[n]
    y_o = (mo.to_quaternion() @ Vector((0, 1, 0))).normalized()
    z_o = (mo.to_quaternion() @ Vector((0, 0, 1))).normalized()
    dy = math.degrees(y_o.angle(my_m))
    dz = math.degrees(z_o.angle(mz_m))
    lr = our_len[n] / (mb.length * 0.01) if mb.length > 0.001 else 0
    lines.append(f"{n:<28} {dy:>7.2f} {dz:>7.2f} {lr:>7.3f}  我们z=({z_o.x:.2f},{z_o.y:.2f},{z_o.z:.2f}) mixz=({mz_m.x:.2f},{mz_m.y:.2f},{mz_m.z:.2f})")
    if dz > 20 or dy > 10:
        big.append(n)
lines.append("")
lines.append(f"问题骨: {len(big)}")
for n in big:
    lines.append(f"  {n}")
lines.append("MAPPING_DONE")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"写入: {OUT}")
