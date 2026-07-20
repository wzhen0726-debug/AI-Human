"""
修复版：QuadriFlow + Rigify
mesh_area ~0.005 对应 ~25K quads
"""
import bpy, os, time

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"

# ============================================================
print("导入...")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type=='MESH': tripo=obj; break

orig_v = len(tripo.data.vertices)
orig_f = len(tripo.data.polygons)
print(f"原始: {orig_v:,}v {orig_f:,}f")

bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ============================================================
print("\n精简...")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
ratio = 100000 / len(tripo.data.vertices)
bpy.ops.mesh.decimate(ratio=min(ratio, 0.5))
bpy.ops.object.mode_set(mode='OBJECT')
print(f"精简后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")

# ============================================================
print("\nQuadriFlow (mesh_area=0.005)...")
t0 = time.time()
bpy.ops.object.quadriflow_remesh(
    use_mesh_symmetry=True,
    use_preserve_sharp=True,
    use_preserve_boundary=True,
    mesh_area=0.005,
    seed=0
)
print(f"耗时: {time.time()-t0:.1f}s")
qf_v = len(tripo.data.vertices); qf_f = len(tripo.data.polygons)
quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
print(f"QuadriFlow后: {qf_v:,}v {qf_f:,}f (quads={quads}, tris={tris})")

# 尝试 Tris to Quads 如果还没转换
if quads < qf_f * 0.5:
    print("四边形不足，尝试 Alt-J...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.object.mode_set(mode='OBJECT')
    quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
    tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
    print(f"Alt-J后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f (quads={quads}, tris={tris})")

# ============================================================
print("\nRigify 绑定...")
bpy.ops.object.armature_human_metarig_add()
rig = bpy.context.active_object
rig.name = "MetaRig"

# 缩放骨骼匹配模型
scale_factor = 0.98 / 2.0
rig.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()

# 骨骼移动到模型位置
tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
arm_mod = tripo.modifiers.new("Armature", 'ARMATURE')
arm_mod.object = rig

# 自动蒙皮
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# 生成控制绑定
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.rigify_generate()
bpy.ops.object.mode_set(mode='OBJECT')
print("Rigify 完成")

# ============================================================
print("\n保存...")
out = os.path.join(OUTPUT_DIR, "tripo_final.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)

# GLB
tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_final.glb"),
    use_selection=True, export_format='GLB', export_apply=True
)

print(f"\n完成!")
print(f"原始: {orig_v:,}v {orig_f:,}f")
print(f"精简: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")
print(f"输出: {out}")