"""修复骨骼前缀: 加mixamorig:前缀, 使行走动画F曲线能驱动.
用法: blender -b --python add_mixamo_prefix.py -- --input <blend> [--output <blend> --glb <glb>]
默认处理ARP版."""
import bpy, os, sys

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend")
OUT_GLB = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.glb")

# 解析CLI参数
argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1:]
else:
    args = []
for i, a in enumerate(args):
    if a == "--input" and i + 1 < len(args):
        IN_BLEND = args[i + 1]
    if a == "--output" and i + 1 < len(args):
        OUT_BLEND = args[i + 1]
    if a == "--glb" and i + 1 < len(args):
        OUT_GLB = args[i + 1]
if not OUT_BLEND or OUT_BLEND == os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend"):
    if IN_BLEND != os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.blend"):
        OUT_BLEND = IN_BLEND
        if OUT_GLB == os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp_mixamo.glb"):
            OUT_GLB = IN_BLEND.replace(".blend", ".glb")
print(f"输入: {IN_BLEND}\n输出: {OUT_BLEND}")

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)

arm = None
body = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
    elif o.type == 'MESH' and len(o.vertex_groups) > 0:
        body = o

PREFIX = "mixamorig:"

# 1. 重命名骨骼(加前缀)
renamed_bones = 0
for b in arm.data.bones:
    if not b.name.startswith(PREFIX):
        b.name = PREFIX + b.name
        renamed_bones += 1
print(f"重命名骨骼: {renamed_bones}")

# 2. 重命名顶点组(加前缀)
renamed_vg = 0
for vg in body.vertex_groups:
    if not vg.name.startswith(PREFIX):
        vg.name = PREFIX + vg.name
        renamed_vg += 1
print(f"重命名顶点组: {renamed_vg}")

# 3. 保存
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"保存: {OUT_BLEND}")

# 4. 导出GLB
try:
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format='GLB',
        use_selection=False,
    )
    print(f"GLB: {OUT_GLB}")
except Exception as e:
    print(f"GLB导出失败: {e}")

print(f"最终: {len(arm.data.bones)}骨骼, 前缀={PREFIX}")
print("PREFIX_DONE")
