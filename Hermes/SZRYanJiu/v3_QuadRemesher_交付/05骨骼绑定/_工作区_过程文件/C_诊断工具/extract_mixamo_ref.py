"""提取Mixamo参考骨骼: 名称+层级+数量, 作为对齐标准."""
import bpy, os

MIX = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Mixamo动画文件\T-Pose.fbx"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\mixamo_reference.json"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=MIX)

arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
        break

if not arm:
    print("ERROR: 未找到骨架")
    raise SystemExit(1)

print(f"骨架: {arm.name}, 骨骼数: {len(arm.data.bones)}")

# 提取层级
import json
bones = {}
def walk(bone, depth):
    bones[bone.name] = {
        "parent": bone.parent.name if bone.parent else None,
        "depth": depth,
        "length": round(bone.length, 4),
        "head": [round(v, 4) for v in bone.head_local],
    }
    for c in bone.children:
        walk(c, depth + 1)

for root in arm.data.bones:
    if root.parent is None:
        walk(root, 0)

json.dump(bones, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"已保存: {OUT}")
print(f"\n=== Mixamo骨骼列表 ({len(bones)}) ===")
for name, info in bones.items():
    ind = "  " * info["depth"]
    print(f"{ind}{name} (长度{info['length']:.3f})")
print("\nMIXAMO_REF_DONE")
