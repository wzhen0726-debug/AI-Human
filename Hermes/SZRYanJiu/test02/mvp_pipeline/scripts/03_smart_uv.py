import bpy, os, math

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\output\mvp"
QR_BLEND = os.path.join(OUT_DIR, "step2_qr_remesh.blend")

# === Step 3: Smart UV 暴力投影 ===
print("=== Step 3: Smart UV ===")
bpy.ops.wm.open_mainfile(filepath=QR_BLEND)

# 找到QR低模（名字以Retopo_开头）
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
for m in meshes:
    print(f"  {m.name}: {len(m.data.polygons)}面")

# QR结果是Retopo_开头的物体
qr_obj = [o for o in meshes if o.name.startswith('Retopo_')]
if qr_obj:
    qr_obj = qr_obj[0]
else:
    # fallback: 面数最少的
    qr_obj = min(meshes, key=lambda x: len(x.data.polygons))
print(f"QR低模: {qr_obj.name}, {len(qr_obj.data.polygons)}面")

# 确保选中QR低模
bpy.ops.object.select_all(action='DESELECT')
qr_obj.select_set(True)
bpy.context.view_layer.objects.active = qr_obj

# 进入编辑模式，全选
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

# Smart UV Project
print("执行Smart UV Project (66°, margin=0.03)...")
bpy.ops.uv.smart_project(
    angle_limit=math.radians(66.0),
    island_margin=0.03,
    area_weight=0.0,
    correct_aspect=True,
    scale_to_bounds=False
)

bpy.ops.object.mode_set(mode='OBJECT')

# 统计UV岛数量
uv_layer = qr_obj.data.uv_layers.active
if uv_layer:
    print(f"UV层: {uv_layer.name}")
    # 简单统计：检查UV坐标范围
    import numpy as np
    uvs = np.empty(len(uv_layer.data) * 2, dtype=np.float32)
    uv_layer.data.foreach_get("uv", uvs)
    uvs = uvs.reshape(-1, 2)
    print(f"UV范围: U[{uvs[:,0].min():.3f}, {uvs[:,0].max():.3f}] V[{uvs[:,1].min():.3f}, {uvs[:,1].max():.3f}]")
else:
    print("警告: 无UV层!")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "step3_smart_uv.blend"))
print("DONE_STEP3")
