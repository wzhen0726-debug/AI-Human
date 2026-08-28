"""测量Mixamo参考骨架(原始FBX)的rest姿态规范数据.
测量: ①每骨Y延伸方向(世界) ②Z轴roll方向(世界) ③左右对称骨差异 ④骨长比例.
导出JSON供rig_from_markers_v2.py作roll朝向权威依据."""
import bpy, os, glob, json, math
from mathutils import Vector

OUT = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定",
                   "logs", "mixamo_rest_spec.json")
FBX_GLOB = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\*.fbx"

bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = None
for f in glob.glob(FBX_GLOB):
    if "walk" in f.lower():
        fbx = f
        break
if fbx is None:
    files = glob.glob(FBX_GLOB)
    fbx = files[0] if files else None
print(f"FBX: {fbx}")
bpy.ops.import_scene.fbx(filepath=fbx)

rig = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        if rig is None or len(o.data.bones) > len(rig.data.bones):
            rig = o
print(f"骨架: {rig.name}, {len(rig.data.bones)}骨, 对象旋转={rig.rotation_euler[:]}")

spec = {}
for b in rig.data.bones:
    m = rig.matrix_world @ b.matrix_local
    y = (m.to_quaternion() @ Vector((0, 1, 0))).normalized()
    z = (m.to_quaternion() @ Vector((0, 0, 1))).normalized()
    x = (m.to_quaternion() @ Vector((1, 0, 0))).normalized()
    spec[b.name] = {
        "head": [round(v, 4) for v in m.translation],
        "length": round(b.length, 4),
        "y": [round(v, 4) for v in y],   # 骨延伸方向
        "z": [round(v, 4) for v in z],   # roll方向
        "x": [round(v, 4) for v in x],
        "parent": b.parent.name if b.parent else None,
    }

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"fbx": os.path.basename(fbx), "arm_obj_rot": list(rig.rotation_euler), "bones": spec}, f, indent=1, ensure_ascii=False)
print(f"写入: {OUT}")

# 打印关键骨骼摘要
key = ["mixamorig:Hips", "mixamorig:LeftShoulder", "mixamorig:LeftArm", "mixamorig:LeftForeArm",
       "mixamorig:LeftHand", "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
       "mixamorig:LeftToeBase", "mixamorig:LeftHandThumb1", "mixamorig:LeftHandIndex1"]
for k in key:
    if k in spec:
        s = spec[k]
        print(f"{k:32s} y={s['y']} z={s['z']}")
print("SPEC_DONE")
