"""
修复版：修复非流形问题 → QuadriFlow → Rigify
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

orig_v = len(tripo.data.vertices); orig_f = len(tripo.data.polygons)
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ============================================================
print("\n修复非流形...")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

# 合并重复顶点
bpy.ops.mesh.remove_doubles(threshold=0.0001)

# 统一法线
bpy.ops.mesh.normals_make_consistent(inside=False)

# 填充洞
try:
    bpy.ops.mesh.fill_holes(sides=0)
    print("洞已填充")
except: pass

# 删除松散几何体
bpy.ops.mesh.delete_loose()

bpy.ops.object.mode_set(mode='OBJECT')
print(f"修复后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")

# ============================================================
print("\n精简...")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
ratio = 80000 / len(tripo.data.vertices)
bpy.ops.mesh.decimate(ratio=min(ratio, 0.5))
bpy.ops.object.mode_set(mode='OBJECT')
dc_v = len(tripo.data.vertices); dc_f = len(tripo.data.polygons)
print(f"精简后: {dc_v:,}v {dc_f:,}f")

# 再做一次法线修复
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

# ============================================================
print("\nQuadriFlow...")
t0 = time.time()
try:
    bpy.ops.object.quadriflow_remesh(
        use_mesh_symmetry=True,
        use_preserve_sharp=True,
        use_preserve_boundary=True,
        mesh_area=0.005,
        seed=0
    )
    qf_ok = True
except Exception as e:
    print(f"QuadriFlow 失败: {e}")
    qf_ok = False

qf_v = len(tripo.data.vertices); qf_f = len(tripo.data.polygons)
quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
print(f"QuadriFlow: {qf_v:,}v {qf_f:,}f (quads={quads}, tris={tris}) {time.time()-t0:.1f}s")

# 如果 QuadriFlow 还是失败，用 Alt-J
if not qf_ok or quads < qf_f * 0.3:
    print("QuadriFlow 未生效，使用 Alt-J...")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.object.mode_set(mode='OBJECT')
    quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
    tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
    print(f"Alt-J: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f (quads={quads}, tris={tris})")

# ============================================================
print("\nRigify 绑定...")
bpy.ops.object.armature_human_metarig_add()
rig = bpy.context.active_object
rig.name = "MetaRig"

scale_factor = 0.98 / 2.0
rig.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
arm_mod = tripo.modifiers.new("Armature", 'ARMATURE')
arm_mod.object = rig

bpy.ops.object.parent_set(type='ARMATURE_AUTO')

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.rigify_generate()
bpy.ops.object.mode_set(mode='OBJECT')

# ============================================================
print("\n保存...")
out = os.path.join(OUTPUT_DIR, "tripo_final_fixed.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_final_fixed.glb"),
    use_selection=True, export_format='GLB', export_apply=True
)

qv = len(tripo.data.vertices); qf = len(tripo.data.polygons)
quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)

print(f"\n{'='*60}")
print(f"完成!")
print(f"原始: {orig_v:,}v {orig_f:,}f → {qv:,}v {qf:,}f ({quads} quads, {tris} tris)")
print(f"输出: {out}")