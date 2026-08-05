import bpy, os, math

# === 配置 ===
DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
QR_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
OUT_03 = os.path.join(DELIVERY, "03自动UV")
os.makedirs(OUT_03, exist_ok=True)

print("=== Step 3: Auto UV ===")

bpy.ops.wm.open_mainfile(filepath=QR_BLEND)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"低模: {mesh.name}, {len(mesh.data.polygons)}面")

bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')

# 方案: 在23.5万面高模上，边缘角度>55°会标记过多接缝导致碎岛
# 改用Smart UV Project（角度限制66°，岛边距0.001），在高面数模型上更稳定
# 它能自动处理接缝和岛合并，避免每个面都是碎岛
bpy.ops.uv.smart_project(
    angle_limit=math.radians(66.0),  # 66°角度限制
    island_margin=0.01,              # 岛边距（用户要求0.01）
    area_weight=0.0,                 # 不按面积加权
    correct_aspect=True,             # 校正宽高比
    scale_to_bounds=False            # 不缩放到边界
)
print("Smart UV Project完成 (angle=66°, margin=0.01)")

bpy.ops.object.mode_set(mode='OBJECT')

# 验证UV
import numpy as np
uv = mesh.data.uv_layers.active
uvs = np.empty(len(uv.data)*2, dtype=np.float32)
uv.data.foreach_get('uv', uvs)
uvs = uvs.reshape(-1, 2)
print(f"UV范围: U[{uvs[:,0].min():.3f}, {uvs[:,0].max():.3f}] V[{uvs[:,1].min():.3f}, {uvs[:,1].max():.3f}]")

# 统计UV岛数量
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)
# 通过UV边分割计算岛数量（近似）
uv_layer = bm.loops.layers.uv.active
island_count = 0
visited = set()
for f in bm.faces:
    if f.index in visited:
        continue
    island_count += 1
    stack = [f]
    while stack:
        face = stack.pop()
        if face.index in visited:
            continue
        visited.add(face.index)
        for edge in face.edges:
            for linked in edge.link_faces:
                if linked.index not in visited:
                    stack.append(linked)
bm.free()
print(f"UV岛数量(近似): {island_count}")

# 保存
out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"已保存: {out_blend}")
print("DONE")
