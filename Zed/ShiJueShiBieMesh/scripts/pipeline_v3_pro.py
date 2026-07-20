"""
Tripo → Quad Remesher → Auto-Rig Pro 专业管线
"""
import bpy, os, time, numpy as np

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_verts(obj):
    return np.array([obj.matrix_world @ v.co for v in obj.data.vertices])

# ============================================================
print("="*70)
print("1. 导入 + 缩放到 1.8m")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type == 'MESH': tripo = obj; break

bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

verts = get_verts(tripo)
z_range = verts[:,2].max() - verts[:,2].min()
scale_factor = 1.8 / z_range
tripo.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 脚在 Z=0
verts = get_verts(tripo)
z_min = verts[:,2].min()
for v in tripo.data.vertices: v.co.z -= z_min
tripo.data.update()

verts = get_verts(tripo)
print(f"  缩放后: {len(tripo.data.vertices):,}v, 高={verts[:,2].max()-verts[:,2].min():.3f}m")

# ============================================================
print("\n2. 清理 + 精简")
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.delete_loose()
bpy.ops.mesh.normals_make_consistent(inside=False)

# 精简到 200K 面（Quad Remesher 需要合理的输入）
target = 200000
current = len(tripo.data.polygons)
if current > target:
    ratio = target / current
    bpy.ops.mesh.decimate(ratio=ratio)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"  精简后: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")

# ============================================================
print("\n3. Quad Remesher 四边形化")

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
t0 = time.time()

try:
    bpy.ops.qremesher.remesh()
    print(f"  Quad Remesher 完成: {time.time()-t0:.1f}s")
    qv = len(tripo.data.vertices); qf = len(tripo.data.polygons)
    quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
    tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
    print(f"  结果: {qv:,}v {qf:,}f (quads={quads}, tris={tris})")
except Exception as e:
    print(f"  Quad Remesher 失败: {e}")
    # 回退到 Alt-J
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.object.mode_set(mode='OBJECT')
    qv = len(tripo.data.vertices); qf = len(tripo.data.polygons)
    quads = sum(1 for p in tripo.data.polygons if len(p.vertices)==4)
    tris = sum(1 for p in tripo.data.polygons if len(p.vertices)==3)
    print(f"  回退 Alt-J: {qv:,}v {qf:,}f (quads={quads}, tris={tris})")

# ============================================================
print("\n4. Auto-Rig Pro 绑定")

# 尝试 ARP 的自动绑定流程
try:
    # Step 1: 添加 ARP 人体骨架
    print("  添加 ARP 骨架...")
    bpy.ops.arp.append_arp()
    
    # 找到 ARP 骨架
    arp_rig = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and 'arp' in obj.name.lower():
            arp_rig = obj
            break
    
    if arp_rig:
        print(f"  ARP 骨架: {arp_rig.name}")
        
        # Step 2: 自动缩放
        print("  自动缩放...")
        bpy.ops.arp.auto_scale()
        
        # Step 3: 绑定
        print("  绑定...")
        tripo.select_set(True)
        arp_rig.select_set(True)
        bpy.context.view_layer.objects.active = arp_rig
        bpy.ops.arp.bind_to_rig()
        
        print("  ARP 绑定完成!")
    else:
        print("  未找到 ARP 骨架，回退到 Rigify")
        raise Exception("ARP 骨架未找到")
        
except Exception as e:
    print(f"  ARP 失败: {e}")
    print("  回退到 Rigify...")
    
    # 删除可能残留的 ARP 骨架
    for obj in list(bpy.data.objects):
        if obj.type == 'ARMATURE' and 'arp' in obj.name.lower():
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Rigify 回退
    bpy.ops.object.armature_human_metarig_add()
    rig = bpy.context.active_object
    rig.name = "MetaRig"
    
    verts = get_verts(tripo)
    height = verts[:,2].max() - verts[:,2].min()
    scale = height / 2.0
    rig.scale = (scale, scale, scale)
    rig.location = Vector((0, 0, height * 0.5))
    bpy.context.view_layer.update()
    
    tripo.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = tripo
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.data.objects.remove(rig, do_unlink=True)
    print("  Rigify 回退完成")

# ============================================================
print("\n5. 清理 + 保存")

# 删除多余骨架
rig_ctrl = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE' and 'RIG-' in obj.name:
        rig_ctrl = obj
        break
if not rig_ctrl:
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and 'arp' in obj.name.lower():
            rig_ctrl = obj
            break

wgt_col = bpy.data.collections.new(name="RigWidgets")
main_col = bpy.data.collections.new(name="Character")
bpy.context.scene.collection.children.link(wgt_col)
bpy.context.scene.collection.children.link(main_col)

for obj in list(bpy.data.objects):
    if obj.name.startswith("WGT-"):
        for col in obj.users_collection:
            col.objects.unlink(obj)
        wgt_col.objects.link(obj)

for obj in [tripo, rig_ctrl]:
    if obj:
        for col in obj.users_collection:
            col.objects.unlink(obj)
        main_col.objects.link(obj)

# 删除多余骨架
for obj in list(bpy.data.objects):
    if obj.type == 'ARMATURE' and obj != rig_ctrl:
        if 'RIG-' not in obj.name and 'arp' not in obj.name.lower():
            bpy.data.objects.remove(obj, do_unlink=True)

out = os.path.join(OUTPUT_DIR, "tripo_pro.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_pro.glb"),
    use_selection=True, export_format='GLB', export_apply=True
)

print(f"\n完成: {out}")
print(f"  模型: {len(tripo.data.vertices):,}v {len(tripo.data.polygons):,}f")
print(f"  绑定: {rig_ctrl.name if rig_ctrl else 'N/A'}")