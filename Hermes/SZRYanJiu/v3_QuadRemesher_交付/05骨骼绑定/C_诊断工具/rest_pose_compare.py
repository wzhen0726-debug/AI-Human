"""静止姿态对照: 我们的手写版骨架(06_rig_final.blend) vs Mixamo参考骨架(原始FBX).
逐骨比较(按mixamorig名匹配): ①head位置差 ②骨骼延伸方向差 ③局部Z轴(roll)差.
任一不匹配都会导致动画"开度"错误(旋转在局部系求值, 局部系不同则世界表现不同)."""
import bpy, os, glob, math
from mathutils import Vector, Matrix

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
OUT = os.path.join(BASE, "logs", "rest_pose_compare.txt")
FBX_GLOB = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\*.fbx"

def get_rig_matrices():
    """当前场景骨架的rest姿态世界矩阵."""
    rig = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and not o.name.startswith("Alpha") and o.name != "Armature":
            rig = o
            break
    if rig is None:
        for o in bpy.data.objects:
            if o.type == 'ARMATURE':
                rig = o
                break
    d = {}
    for b in rig.data.bones:
        # rest世界矩阵 = armature世界矩阵 @ 骨骼矩阵
        m = rig.matrix_world @ b.matrix_local
        d[b.name] = m
    return d

# 1) 我们的骨架
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "B_骨骼绑定", "06_rig_final.blend"))
ours = get_rig_matrices()
print(f"我们的骨架: {len(ours)}骨")

# 2) Mixamo参考骨架(导入原始FBX)
bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = None
for f in glob.glob(FBX_GLOB):
    if "walk" in f.lower() or "Walking" in f:
        fbx = f
        break
if fbx is None:
    files = glob.glob(FBX_GLOB)
    fbx = files[0] if files else None
print(f"导入: {fbx}")
bpy.ops.import_scene.fbx(filepath=fbx)
mixamo = get_rig_matrices()
print(f"Mixamo骨架: {len(mixamo)}骨")

# 3) 逐骨对照
lines = []
lines.append(f"我们的骨架: {len(ours)}骨 | Mixamo: {len(mixamo)}骨 | FBX={os.path.basename(fbx)}")
lines.append("")
lines.append(f"{'骨骼':<28} {'位置差m':>8} {'方向差°':>8} {'Z轴差°':>8}")
common = sorted(set(ours) & set(mixamo))
lines.append(f"同名骨: {len(common)}")
bad = []
for n in common:
    mo, mm = ours[n], mixamo[n]
    pos_diff = (mo.translation - mm.translation).length
    # 骨骼延伸方向 = Y轴(bone延伸方向是局部Y)
    dir_o = mo.to_quaternion() @ Vector((0, 1, 0))
    dir_m = mm.to_quaternion() @ Vector((0, 1, 0))
    ang_dir = math.degrees(dir_o.angle(dir_m))
    # roll轴 = 局部Z
    z_o = mo.to_quaternion() @ Vector((0, 0, 1))
    z_m = mm.to_quaternion() @ Vector((0, 0, 1))
    ang_z = math.degrees(z_o.angle(z_m))
    lines.append(f"{n:<28} {pos_diff:>8.3f} {ang_dir:>8.2f} {ang_z:>8.2f}")
    if ang_z > 20 or ang_dir > 5:
        bad.append(n)
lines.append("")
lines.append(f"问题骨(方向>5°或Z轴>20°): {len(bad)}")
for n in bad:
    lines.append(f"  {n}")
lines.append("REST_COMPARE_DONE")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"写入: {OUT}")
