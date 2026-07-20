"""
Tripo 模型 → 合规数字人
QuadriFlow 四边形化 + Auto-Rig Pro 绑定
"""
import bpy, os, time, json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"

# ============================================================
print("="*60)
print("1. 导入 + 检查")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type=='MESH': tripo=obj; break

orig_verts = len(tripo.data.vertices)
orig_faces = len(tripo.data.polygons)
print(f"原始: {orig_verts:,} verts, {orig_faces:,} faces")

# 应用变换
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

vs = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
print(f"尺寸: {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} x {max(zs)-min(zs):.2f}m")

# ============================================================
print("\n"+"="*60)
print("2. 精简（Decimate → ~150K）")

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

# 先合并重复顶点
bpy.ops.mesh.remove_doubles(threshold=0.0001)

# Decimate
target_ratio = 150000 / len(tripo.data.vertices)
print(f"目标 ratio: {target_ratio:.4f}")
bpy.ops.mesh.decimate(ratio=target_ratio)
bpy.ops.object.mode_set(mode='OBJECT')

dc_verts = len(tripo.data.vertices)
dc_faces = len(tripo.data.polygons)
print(f"精简后: {dc_verts:,} verts, {dc_faces:,} faces")

# ============================================================
print("\n"+"="*60)
print("3. QuadriFlow → 四边形化 (~25K quads)")

bpy.ops.object.mode_set(mode='OBJECT')

t0 = time.time()
try:
    bpy.ops.object.quadriflow_remesh(
        use_mesh_symmetry=True,
        use_preserve_sharp=True,
        use_preserve_boundary=True,
        mesh_area=0.00025
    )
except Exception as e:
    print(f"QuadriFlow 报错: {e}")
    bpy.ops.object.quadriflow_remesh(
        use_mesh_symmetry=True,
        use_preserve_sharp=False,
        use_preserve_boundary=True,
        mesh_area=0.0005
    )
print(f"QuadriFlow 完成: {time.time()-t0:.1f}s")

qf_verts = len(tripo.data.vertices)
qf_faces = len(tripo.data.polygons)
print(f"四边形化后: {qf_verts:,} verts, {qf_faces:,} faces")

# 检查四边形占比
quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
print(f"四边面: {quads}, 三角面: {tris}")

# ============================================================
print("\n"+"="*60)
print("4. 自动 Rigify 绑定")

# 用 Rigify（Blender 内置）做基础绑定
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)

# 添加人体 meta-rig
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.armature_human_metarig_add()

rig = bpy.context.active_object
print(f"Meta-Rig: {rig.name}")

# 尝试让骨骼匹配模型尺寸
# 模型尺寸约 0.98m 高，人体 meta-rig 默认约 2m 高
# 需要缩放
scale_factor = 0.98 / 2.0
rig.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()

# 给模型加 Armature 修改器
arm_mod = tripo.modifiers.new("Armature", 'ARMATURE')
arm_mod.object = rig

# 用自动权重绑定
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
tripo.select_set(True)
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print("自动权重绑定完成")

# 生成 Rigify 控制绑定
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
try:
    bpy.ops.pose.rigify_generate()
    print("Rigify 控制绑定生成完成")
except Exception as e:
    print(f"Rigify 生成失败: {e}")

bpy.ops.object.mode_set(mode='OBJECT')

# ============================================================
print("\n"+"="*60)
print("5. 保存最终结果")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR, "tripo_retopologized_rigged.blend"))
print(f"已保存: tripo_retopologized_rigged.blend")

# 导出 GLB
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_final.glb"),
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
print(f"已导出 GLB: tripo_final.glb")

# 总结
print(f"\n{'='*60}")
print(f"管线完成:")
print(f"  原始: {orig_verts:,} verts, {orig_faces:,} faces")
print(f"  精简: {dc_verts:,} verts, {dc_faces:,} faces")
print(f"  四边形化: {qf_verts:,} verts, {qf_faces:,} faces ({quads} quads, {tris} tris)")
print(f"  绑定: Rigify 自动骨骼 + 蒙皮")