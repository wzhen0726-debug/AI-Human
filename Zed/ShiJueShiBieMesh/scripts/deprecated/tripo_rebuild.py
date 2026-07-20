"""
从头重建：Tripo → 精简 → 骨骼对齐 → Rigify
"""
import bpy, os, time, numpy as np
from mathutils import Vector

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_tripo"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"

# ============================================================
print("1. 导入 + 清理")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type=='MESH': tripo=obj; break

bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 检查包围盒
vs = np.array([tripo.matrix_world @ v.co for v in tripo.data.vertices])
print(f"原始: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")
print(f"BBox: X[{vs[:,0].min():.2f},{vs[:,0].max():.2f}] Y[{vs[:,1].min():.2f},{vs[:,1].max():.2f}] Z[{vs[:,2].min():.2f},{vs[:,2].max():.2f}]")
center_y = (vs[:,1].min() + vs[:,1].max()) / 2
height = vs[:,1].max() - vs[:,1].min()
print(f"高度: {height:.2f}m, 中心Y: {center_y:.2f}")

# 判断姿态：如果X范围远大于Z范围 → T-pose；如果差不多 → 站姿
x_range = vs[:,0].max() - vs[:,0].min()
z_range = vs[:,2].max() - vs[:,2].min()
print(f"X范围: {x_range:.2f}m, Z范围: {z_range:.2f}m")
is_tpose = x_range > z_range * 1.5
print(f"姿态: {'T-Pose/A-Pose' if is_tpose else '站姿/不确定'}")

# ============================================================
print("\n2. 精简")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.normals_make_consistent(inside=False)
ratio = 60000 / len(tripo.data.vertices)
bpy.ops.mesh.decimate(ratio=min(ratio, 0.5))
bpy.ops.object.mode_set(mode='OBJECT')
print(f"精简后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")

# Alt-J 四边形转换
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.tris_convert_to_quads()
bpy.ops.object.mode_set(mode='OBJECT')
quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
print(f"Alt-J: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f ({quads}Q {tris}T)")

# ============================================================
print("\n3. 放置 Rigify Meta-Rig")

# 确保没有物体被选中
bpy.ops.object.select_all(action='DESELECT')

# 添加 human meta-rig
bpy.ops.object.armature_human_metarig_add()
rig = bpy.context.active_object
rig.name = "MetaRig"

# 把 meta-rig 移到模型位置 + 缩放匹配
scale = height / 2.0  # Rigify meta-rig 默认 ~2m 高
rig.scale = (scale, scale, scale)
rig.location = Vector((0, 0, 0))  # 模型在原点
bpy.context.view_layer.update()

print(f"MetaRig: loc={list(rig.location)}, scale={scale:.3f}")

# ============================================================
print("\n4. 绑定设置")

# 先确保 MetaRig 不 parent 到任何东西
rig.parent = None

# 给 mesh 加 Armature modifier
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)

# 删除旧的修改器
for mod in list(tripo.modifiers):
    tripo.modifiers.remove(mod)

# 加新的 Armature
arm_mod = tripo.modifiers.new("Armature", 'ARMATURE')
arm_mod.object = rig

# 自动权重绑定
rig.select_set(True)
tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print("自动权重完成")

# ============================================================
print("\n5. 生成 Rigify 控制绑定")

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.rigify_generate()
bpy.ops.object.mode_set(mode='OBJECT')

# 把生成的 WGT 对象放入集合
rig_ctrl = None
for obj in bpy.data.objects:
    if obj.type=='ARMATURE' and 'RIG' in obj.name.upper():
        rig_ctrl = obj
        break

if rig_ctrl:
    print(f"控制绑定: {rig_ctrl.name}")
    # 创建 WGT 集合
    wgt_col = bpy.data.collections.get("RigWidgets")
    if not wgt_col:
        wgt_col = bpy.data.collections.new("RigWidgets")
        bpy.context.scene.collection.children.link(wgt_col)
    
    for obj in bpy.data.objects:
        if obj.name.startswith("WGT-"):
            # 从主集合移除
            for col in obj.users_collection:
                col.objects.unlink(obj)
            wgt_col.objects.link(obj)
    print(f"WGT对象已移至 RigWidgets 集合")

# 把 MetaRig 放入集合
meta_col = bpy.data.collections.get("MetaRig_Original")
if not meta_col:
    meta_col = bpy.data.collections.new("MetaRig_Original")
    bpy.context.scene.collection.children.link(meta_col)
# Move MetaRig to this collection
if rig and rig.name == "MetaRig":
    for col in rig.users_collection:
        col.objects.unlink(rig)
    meta_col.objects.link(rig)

# 模型放入主集合
main_col = bpy.data.collections.get("Character")
if not main_col:
    main_col = bpy.data.collections.new("Character")
    bpy.context.scene.collection.children.link(main_col)
for col in tripo.users_collection:
    col.objects.unlink(tripo)
main_col.objects.link(tripo)
if rig_ctrl:
    for col in rig_ctrl.users_collection:
        col.objects.unlink(rig_ctrl)
    main_col.objects.link(rig_ctrl)

# ============================================================
print("\n6. 保存")
out = os.path.join(OUTPUT_DIR, "tripo_clean.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_clean.glb"),
    use_selection=True, export_format='GLB', export_apply=True
)

print(f"\n完成! 输出: {out}")
print(f"  模型: {len(tripo.data.vertices):,}v ({quads}Q/{tris}T)")
print(f"  骨骼: Rigify 控制绑定")
print(f"  集合: Character / RigWidgets / MetaRig_Original")