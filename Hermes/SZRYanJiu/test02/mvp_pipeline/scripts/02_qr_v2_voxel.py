import bpy, os, bmesh

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\mvp_pipeline\output"
HIGH_POLY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\tripoTpose_01_repair.blend"

print("=== 方案2: Voxel Remesh + Decimate ===")

bpy.ops.wm.open_mainfile(filepath=HIGH_POLY)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"原始: {len(mesh.data.polygons)}面")

bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh

# Voxel Remesh: 体素大小0.002m (2mm)，保留细节
mesh.data.remesh_voxel_size = 0.002
bpy.ops.object.voxel_remesh()
print(f"Voxel Remesh后: {len(mesh.data.polygons)}面")

# Quadriflow Remesh: 三角面→quad，目标150K面
bpy.ops.object.quadriflow_remesh(
    use_mesh_symmetry=False,
    use_preserve_sharp=False,
    use_preserve_boundary=False,
    smooth_normals=False,
    mode='FACES',
    target_faces=150000,
    seed=0
)
print(f"Quadriflow后: {len(mesh.data.polygons)}面")

# 检查
bm = bmesh.new()
bm.from_mesh(mesh.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
print(f"非流形边: {non_manifold}")

# 验证（Quadriflow后不需要Decimate）
bm = bmesh.new()
bm.from_mesh(mesh.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
quads = sum(1 for p in mesh.data.polygons if len(p.vertices) == 4)
bm.free()

print(f"quad: {quads/len(mesh.data.polygons)*100:.1f}%")
print(f"非流形边: {non_manifold}")

# 区域分布
head = hand = other = 0
for p in mesh.data.polygons:
    vs = [mesh.data.vertices[i] for i in p.vertices]
    avg_z = sum(v.co.z for v in vs) / len(vs)
    max_x = max(abs(v.co.x) for v in vs)
    if avg_z > 0.8: head += 1
    elif max_x > 0.35 and avg_z > 0.7: hand += 1
    else: other += 1

print(f"头部: {head} ({head/len(mesh.data.polygons)*100:.1f}%)")
print(f"手部: {hand} ({hand/len(mesh.data.polygons)*100:.1f}%)")
print(f"其他: {other} ({other/len(mesh.data.polygons)*100:.1f}%)")

mesh.name = "MVP_LowPoly_v2"

# 保存
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "02_qr_v2_voxel.blend"))
fbx_out = os.path.join(OUT_DIR, "02_qr_v2_voxel.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_out, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"已保存: 02_qr_v2_voxel.blend/fbx")
print("DONE")
