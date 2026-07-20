"""
创建干净的模板文件给用户打点
"""
import bpy

TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
OUTPUT = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\template_clean.blend"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath=TEMPLATE)

template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH': template_obj = obj; break

# 把之前自动检测的候选顶点高亮出来，方便你验证
candidates = {
    'nose_tip': 7883, 'left_eye_inner': 5318, 'left_eye_outer': 6499,
    'right_eye_inner': 948, 'right_eye_outer': 2166, 'left_mouth_corner': 7990,
    'right_mouth_corner': 3688, 'chin': 8262, 'nose_bridge': 7708,
    'forehead': 7693, 'left_brow': 4432, 'right_brow': 477
}

vg = template_obj.vertex_groups.new(name="AUTO_DETECTED")
for name, idx in candidates.items():
    vg.add([idx], 1.0, 'REPLACE')

print(f"候选顶点已加入顶点组 'AUTO_DETECTED'")

bpy.ops.wm.save_as_mainfile(filepath=OUTPUT)
print(f"保存: {OUTPUT}")
print(f"顶点数: {len(template_obj.data.vertices)}")