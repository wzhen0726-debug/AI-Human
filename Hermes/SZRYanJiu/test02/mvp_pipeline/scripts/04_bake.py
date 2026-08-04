import bpy, os

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\output\mvp"
UV_BLEND = os.path.join(OUT_DIR, "step3_smart_uv.blend")

print("=== Step 4: Bake (v2) ===")
bpy.ops.wm.open_mainfile(filepath=UV_BLEND)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
high_poly = [o for o in meshes if not o.name.startswith('Retopo_')][0]
low_poly = [o for o in meshes if o.name.startswith('Retopo_')][0]
print(f"高模: {high_poly.name} ({len(high_poly.data.polygons)}面)")
print(f"低模: {low_poly.name} ({len(low_poly.data.polygons)}面)")

# 检查高模法线
import bmesh
bm = bmesh.new()
bm.from_mesh(high_poly.data)
bm.faces.ensure_lookup_table()
up_count = sum(1 for f in bm.faces if f.normal.z > 0)
total = len(bm.faces)
print(f"高模法线朝上: {up_count}/{total} ({up_count/total*100:.1f}%)")
bm.free()

# 设置渲染引擎
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False

# GPU
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    cprefs = prefs.preferences
    cprefs.compute_device_type = 'NONE'
bpy.context.scene.cycles.device = 'CPU'
print("使用CPU渲染（避免GPU兼容问题）")

# 给低模创建新材质
mat = bpy.data.materials.new(name="MVP_Material")
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

img = bpy.data.images.new("MVP_Diffuse", width=2048, height=2048, alpha=False)
tex.image = img

nt.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

# Bake设置
bpy.context.scene.render.bake.use_pass_direct = False
bpy.context.scene.render.bake.use_pass_indirect = False
bpy.context.scene.render.bake.use_pass_color = True
bpy.context.scene.render.bake.margin = 16

# Selected to Active
bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly

# 确保tex节点是active
nt.nodes.active = tex

# 设置bake参数
bpy.context.scene.render.bake.use_selected_to_active = True
bpy.context.scene.render.bake.cage_extrusion = 0.05  # 5cm cage
bpy.context.scene.render.bake.max_ray_distance = 0.1  # 10cm ray distance

print("开始Diffuse烘焙...")
print(f"  分辨率: 2048x2048, Margin: 16px, Cage: 0.05m, Ray: 0.1m")

bpy.ops.object.bake(type='DIFFUSE', save_mode='EXTERNAL')

# 保存贴图
img.filepath_raw = os.path.join(OUT_DIR, "mvp_diffuse_2k.png")
img.file_format = 'PNG'
img.save()
print(f"Diffuse贴图已保存: {img.filepath_raw}")

# 检查贴图不是全黑
import numpy as np
pixels = np.array(img.pixels[:])
print(f"贴图像素统计: min={pixels.min():.3f}, max={pixels.max():.3f}, mean={pixels.mean():.3f}")
if pixels.max() < 0.01:
    print("⚠️ 警告: 贴图接近全黑!")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "step4_bake.blend"))
print("DONE_STEP4")
