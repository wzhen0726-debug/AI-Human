import bpy, os, sys, tempfile
import pymeshlab as ml

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\mvp_pipeline\output"
HIGH_POLY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\tripoTpose_01_repair.blend"

print("=== 方案3: Instant Meshes (pymeshlab) ===")

# 从Blender导出FBX供pymeshlab使用
print("导出FBX...")
bpy.ops.wm.open_mainfile(filepath=HIGH_POLY)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]

fbx_path = os.path.join(tempfile.gettempdir(), "hermes_instant_input.fbx")
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.export_scene.fbx(
    filepath=fbx_path, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='OFF', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"FBX已导出: {fbx_path}")

# pymeshlab处理
print("\npymeshlab处理...")
ms = ml.MeshSet()
ms.load_new_mesh(fbx_path)

print(f"输入: {ms.current_mesh().face_number()}面")

# 各向同性显式重网格 (Instant Meshes核心算法)
# targetlen: 目标边长 (0.3% of bbox diagonal，更密)
ms.meshing_isotropic_explicit_remeshing(
    targetlen=ml.PercentageValue(0.3),
    featuredeg=30.0,
    adaptive=True
)

print(f"重网格后: {ms.current_mesh().face_number()}面")

# 如果面数不够，再细分
if ms.current_mesh().face_number() < 100000:
    ms.meshing_isotropic_explicit_remeshing(
        targetlen=ml.PercentageValue(0.15),
        featuredeg=30.0,
        adaptive=True
    )
    print(f"二次重网格后: {ms.current_mesh().face_number()}面")

# 如果需要减面
if ms.current_mesh().face_number() > 200000:
    ratio = 150000 / ms.current_mesh().face_number()
    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=150000,
        preservenormal=True
    )
    print(f"减面后: {ms.current_mesh().face_number()}面")

# 保存三角面结果供Blender Quadriflow处理
tri_fbx = os.path.join(tempfile.gettempdir(), "hermes_instant_tri.fbx")
ms.save_current_mesh(tri_fbx)
print(f"三角面结果: {tri_fbx}")

# 导入Blender
print("\n导入Blender...")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=tri_fbx)
tri_mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"导入: {len(tri_mesh.data.polygons)}面")

# 用Blender Quadriflow转quad
bpy.ops.object.select_all(action='DESELECT')
tri_mesh.select_set(True)
bpy.context.view_layer.objects.active = tri_mesh
bpy.ops.object.quadriflow_remesh(
    use_mesh_symmetry=False,
    use_preserve_sharp=False,
    use_preserve_boundary=False,
    smooth_normals=False,
    mode='FACES',
    target_faces=150000,
    seed=0
)
qr = tri_mesh
print(f"Quadriflow后: {len(qr.data.polygons)}面")

# 验证
import bmesh
bm = bmesh.new()
bm.from_mesh(qr.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
quads = sum(1 for p in qr.data.polygons if len(p.vertices) == 4)
bm.free()

print(f"quad: {quads/len(qr.data.polygons)*100:.1f}%")
print(f"非流形边: {non_manifold}")

# 区域分布
head = hand = other = 0
for p in qr.data.polygons:
    vs = [qr.data.vertices[i] for i in p.vertices]
    avg_z = sum(v.co.z for v in vs) / len(vs)
    max_x = max(abs(v.co.x) for v in vs)
    if avg_z > 0.8: head += 1
    elif max_x > 0.35 and avg_z > 0.7: hand += 1
    else: other += 1

print(f"头部: {head} ({head/len(qr.data.polygons)*100:.1f}%)")
print(f"手部: {hand} ({hand/len(qr.data.polygons)*100:.1f}%)")
print(f"其他: {other} ({other/len(qr.data.polygons)*100:.1f}%)")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "02_qr_v3_instant.blend"))
fbx_out = os.path.join(OUT_DIR, "02_qr_v3_instant.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_out, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"已保存: 02_qr_v3_instant.blend/fbx")
print("DONE")
