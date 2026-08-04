import bpy, os

HIGH_POLY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\tripoTpose_01_repair.blend"
OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\mvp_pipeline\output"

print("=== 方案1: Decimate预处理 + QR ===")

bpy.ops.wm.open_mainfile(filepath=HIGH_POLY)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"原始: {len(mesh.data.polygons)}面")

bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh

# 创建顶点组标记头/手（高保真区域）
vg = mesh.vertex_groups.new(name="HighDetail")

# 头: Z>0.8, 手: |X|>0.35且Z>0.7
head_hand_verts = []
for v in mesh.data.vertices:
    if v.co.z > 0.8 or (abs(v.co.x) > 0.35 and v.co.z > 0.7):
        head_hand_verts.append(v.index)

print(f"头/手顶点: {len(head_hand_verts)}")
vg.add(head_hand_verts, 1.0, 'REPLACE')

# Decimate修改器: 身体部分 collapse_ratio=0.3 (保留30%), 头/手不受影响
mod = mesh.modifiers.new("Decimate", 'DECIMATE')
mod.ratio = 0.3
mod.use_collapse_triangulate = True
mod.vertex_group = "HighDetail"
mod.invert_vertex_group = True  # 反转: 只影响非头/手区域

print("应用Decimate (身体30%, 头/手保留)...")
bpy.ops.object.modifier_apply(modifier="Decimate")

print(f"Decimate后: {len(mesh.data.polygons)}面")

# 保存预处理结果
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "01_decimate_pre_qr.blend"))

# 导出FBX供QR
fbx_path = os.path.join(OUT_DIR, "01_decimate_pre_qr.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_path, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='OFF', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"FBX已导出: {fbx_path}")
print("DONE")
