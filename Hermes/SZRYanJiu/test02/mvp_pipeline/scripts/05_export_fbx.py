import bpy, os

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\output\mvp"
BAKE_BLEND = os.path.join(OUT_DIR, "step4_bake.blend")
DIFFUSE_TEX = os.path.join(OUT_DIR, "mvp_diffuse_2k.png")

print("=== Step 5: 导出FBX（含贴图） ===")
bpy.ops.wm.open_mainfile(filepath=BAKE_BLEND)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
low_poly = [o for o in meshes if o.name.startswith('Retopo_')][0]
print(f"低模: {low_poly.name} ({len(low_poly.data.polygons)}面)")

# 确保材质中的贴图指向正确的文件路径
mat = low_poly.data.materials[0]
if mat and mat.use_nodes:
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            # 重新加载贴图文件
            img = node.image
            img.filepath = DIFFUSE_TEX
            img.reload()
            print(f"贴图已关联: {img.filepath}")

# 删除高模（减小FBX体积）——先收集名字再删
high_poly_names = [o.name for o in meshes if not o.name.startswith('Retopo_')]
for name in high_poly_names:
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
        print(f"已删除高模: {name}")

# 只导出低模
bpy.ops.object.select_all(action='DESELECT')
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly

fbx_path = os.path.join(OUT_DIR, "mvp_for_mixamo.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    use_mesh_modifiers=True,
    mesh_smooth_type='FACE',
    use_tspace=True,
    use_custom_props=False,
    add_leaf_bones=False,
    bake_anim=False,
    use_armature_deform_only=True,
    path_mode='COPY',  # 复制贴图到FBX同目录
    embed_textures=True  # 嵌入贴图
)
print(f"FBX已导出: {fbx_path}")
print(f"文件大小: {os.path.getsize(fbx_path)/1024/1024:.1f}MB")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "step5_export_fbx.blend"))
print("DONE_STEP5")
