import bpy, os, math

# === 配置 ===
DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
QR_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend")
OUT_03 = os.path.join(DELIVERY, "03自动UV_rim_bevel")
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
# 改用Smart UV Project（角度限制66°，岛边距0.01），在高面数模型上更稳定
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

# 统计UV岛数量 (修复08-05: 旧版BFS走几何邻接忽略UV接缝, 连通网格恒报1岛, 指标失真)
# 正确做法: 共享边两侧loop的UV坐标一致(无接缝)才算同一岛
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.faces.ensure_lookup_table()
uv_layer = bm.loops.layers.uv.active
EPS = 1e-6

# 每面每顶点的UV坐标 (一个loop对应一个vert)
face_vert_uv = {}
for f in bm.faces:
    d = {}
    for l in f.loops:
        uvc = l[uv_layer].uv
        d[l.vert.index] = (uvc.x, uvc.y)
    face_vert_uv[f.index] = d

# 无接缝邻接表: 边两侧面在两端点处UV一致 → 同岛
adj = {f.index: [] for f in bm.faces}
for e in bm.edges:
    lf = e.link_faces
    if len(lf) != 2:
        continue
    f1, f2 = lf
    v1, v2 = e.verts[0].index, e.verts[1].index
    a1, a2 = face_vert_uv[f1.index].get(v1), face_vert_uv[f1.index].get(v2)
    b1, b2 = face_vert_uv[f2.index].get(v1), face_vert_uv[f2.index].get(v2)
    if a1 and a2 and b1 and b2:
        if (abs(a1[0]-b1[0]) < EPS and abs(a1[1]-b1[1]) < EPS and
                abs(a2[0]-b2[0]) < EPS and abs(a2[1]-b2[1]) < EPS):
            adj[f1.index].append(f2.index)
            adj[f2.index].append(f1.index)

island_count = 0
visited = set()
sizes = []
for fi in adj:
    if fi in visited:
        continue
    island_count += 1
    stack = [fi]
    size = 0
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        size += 1
        stack.extend(adj[cur])
    sizes.append(size)
bm.free()

sizes.sort(reverse=True)
print(f"UV岛数量: {island_count} (最大岛{sizes[0]}面, 前5: {sizes[:5]})")

# 保存
out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"已保存: {out_blend}")
print("DONE")
