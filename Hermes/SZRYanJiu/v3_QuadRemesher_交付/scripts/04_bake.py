import bpy, os
import numpy as np

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
UV_BLEND = os.path.join(DELIVERY, "03自动UV", "03_auto_uv.blend")
HIGH_POLY = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
FIXED_TEX = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_original_tex_fixed.png")
OUT_04 = os.path.join(DELIVERY, "04纹理烘焙")
os.makedirs(OUT_04, exist_ok=True)

print("=== Step 4: Bake 4K (修复贴图) ===")

# 加载低模(UV已展开)
bpy.ops.wm.open_mainfile(filepath=UV_BLEND)
low_poly = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"低模: {low_poly.name}, {len(low_poly.data.polygons)}面")

# 导入高模
with bpy.data.libraries.load(HIGH_POLY) as (data_from, data_to):
    data_to.objects = data_from.objects
for obj in data_to.objects:
    bpy.context.collection.objects.link(obj)
high_poly = [o for o in bpy.data.objects if o.type == 'MESH' and o != low_poly][0]

# 高模贴图检查（blend里已内嵌贴图，无需外部替换）
# 如果存在修复贴图则替换，否则直接使用高模自带贴图
tex_replaced = 0
for mat in high_poly.data.materials:
    if mat and mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                img_name_lower = node.image.name.lower()
                if any(k in img_name_lower for k in ['basecolor', 'diffuse', 'albedo', 'color', 'tex']):
                    old_name = node.image.name
                    # 如果存在修复贴图则替换，否则保留原贴图
                    if os.path.exists(FIXED_TEX):
                        new_img = bpy.data.images.load(FIXED_TEX)
                        new_img.name = old_name
                        node.image = new_img
                        tex_replaced += 1
                        print(f"高模贴图替换(修复版): {old_name}")
                    else:
                        print(f"使用高模自带贴图: {old_name} ({node.image.size[0]}x{node.image.size[1]})")
if tex_replaced == 0:
    print("使用高模内嵌贴图（无外部替换）")

# Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.cycles.device = 'CPU'

# 低模材质
mat = bpy.data.materials.new(name='MVP_Material')
mat.use_nodes = True
if low_poly.data.materials:
    low_poly.data.materials[0] = mat
else:
    low_poly.data.materials.append(mat)
nt = mat.node_tree
nt.nodes.clear()
output = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
tex = nt.nodes.new('ShaderNodeTexImage')
img = bpy.data.images.new('MVP_Diffuse_4K', width=4096, height=4096, alpha=False)
tex.image = img
nt.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

# Bake Diffuse
bpy.context.scene.render.bake.use_pass_direct = False
bpy.context.scene.render.bake.use_pass_indirect = False
bpy.context.scene.render.bake.use_pass_color = True
bpy.context.scene.render.bake.margin = 16
bpy.context.scene.render.bake.use_selected_to_active = True
bpy.context.scene.render.bake.cage_extrusion = 0.01   # 原0.005，增大避免黑色斑块
bpy.context.scene.render.bake.max_ray_distance = 0.05  # 原0.01，增大投射距离

bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
nt.nodes.active = tex

print('烘焙Diffuse中 (4K, cage=0.01, ray=0.05)...')
bpy.ops.object.bake(type='DIFFUSE')

tex_path = os.path.join(OUT_04, "04_diffuse_4k.png")
img.filepath_raw = tex_path
img.file_format = 'PNG'
img.save()

pixels = np.array(img.pixels[:])
print(f"Diffuse贴图: min={pixels.min():.3f}, max={pixels.max():.3f}, mean={pixels.mean():.3f}")

# Bake Normal (方案md要求)
print('\\n烘焙Normal中 (4K)...')
# 创建Normal贴图节点
normal_tex = nt.nodes.new('ShaderNodeTexImage')
normal_img = bpy.data.images.new('MVP_Normal_4K', width=4096, height=4096, alpha=False)
normal_tex.image = normal_img
# 连接Normal到BSDF
normal_map = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
nt.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
nt.nodes.active = normal_tex

bpy.ops.object.bake(type='NORMAL')

normal_path = os.path.join(OUT_04, "04_normal_4k.png")
normal_img.filepath_raw = normal_path
normal_img.file_format = 'PNG'
normal_img.save()
print(f"Normal贴图已保存")

# 断开Normal连接（避免影响FBX导出）
# Blender 5.1: links.remove() 只接受1个link参数，且遍历前需拷贝列表
for link in list(nt.links):
    if link.to_node == bsdf and link.to_socket.name == 'Normal':
        nt.links.remove(link)
for link in list(nt.links):
    if link.from_node == normal_tex:
        nt.links.remove(link)

# 删除高模
bpy.data.objects.remove(high_poly, do_unlink=True)

# 导出FBX
fbx_path = os.path.join(OUT_04, "05_for_mixamo.fbx")
bpy.ops.object.select_all(action='DESELECT')
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
bpy.ops.export_scene.fbx(
    filepath=fbx_path, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=True, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='COPY', embed_textures=True
)

# 保存blend
out_blend = os.path.join(OUT_04, "04_bake.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

print(f"\n=== 完成 ===")
print(f"贴图(4K): {tex_path}")
print(f"FBX: {fbx_path}")
print(f"Blend: {out_blend}")
print("DONE")
