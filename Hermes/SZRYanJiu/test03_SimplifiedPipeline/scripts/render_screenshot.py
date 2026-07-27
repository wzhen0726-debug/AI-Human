"""渲染高模修复后的模型截图 — 正面+侧面+3/4视角"""
import bpy, sys, os, math
from mathutils import Vector

obj = None
for o in bpy.data.objects:
    if o.type == 'MESH':
        obj = o
        break

if not obj:
    print("ERROR: No mesh")
    sys.exit(1)

# 获取模型尺寸和中心 (用局部坐标计算, 再转世界坐标)
local_verts = [v.co for v in obj.data.vertices]
xs = [v.x for v in local_verts]
ys = [v.y for v in local_verts]
zs = [v.z for v in local_verts]
mn = (min(xs), min(ys), min(zs))
mx = (max(xs), max(ys), max(zs))
dims = (mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2])
local_center = Vector(((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2))
# 转世界坐标
world_center = obj.matrix_world @ local_center
print(f"model center (local): ({local_center.x:.4f}, {local_center.y:.4f}, {local_center.z:.4f})")
print(f"model center (world): ({world_center.x:.4f}, {world_center.y:.4f}, {world_center.z:.4f})")
print(f"model dims (local): ({dims[0]:.4f}, {dims[1]:.4f}, {dims[2]:.4f})")

# 设置渲染参数
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'VERTEX'
scene.display.shading.show_cavity = True

# 设置顶点颜色为浅色 (只设部分验证, 避免193万面循环超时)
if not obj.data.vertex_colors:
    obj.data.vertex_colors.new()
vc = obj.data.vertex_colors[0]
# 只设前1000个loop验证
for i in range(min(1000, len(vc.data))):
    vc.data[i].color = (0.7, 0.7, 0.7, 1.0)

# 确保有相机 (在场景中持久化)
cam = bpy.data.objects.get("Camera")
if not cam:
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    # 链接到场景集合
    scene.collection.objects.link(cam)
    scene.camera = cam
    # 确保视图层更新
    bpy.context.view_layer.objects.active = cam
    cam.select_set(True)
    bpy.context.view_layer.update()

# 输出目录
out_dir = os.path.dirname(bpy.data.filepath)
angles = [
    ("front", 0, 0),           # 正面
    ("side", math.pi/2, 0),    # 侧面
    ("three_quarter", math.pi/4, math.pi/6),  # 3/4视角
]

for name, rot_y, rot_z in angles:
    # 相机位置: 以世界中心为基准, 距离 = 最大维度 * 1.5 (确保全身入画)
    dist = max(dims) * 1.5
    # 正面: 相机在模型前方 (-Y方向, 因为face朝-Y)
    if name == "front":
        cam_pos = Vector((world_center.x, world_center.y - dist, world_center.z))
    # 侧面: 相机在模型右侧 (+X方向)
    elif name == "side":
        cam_pos = Vector((world_center.x + dist, world_center.y, world_center.z))
    # 3/4: 右前方
    else:
        cam_pos = Vector((world_center.x + dist*0.7, world_center.y - dist*0.7, world_center.z + dist*0.3))
    
    cam.location = cam_pos
    
    # 相机看向世界中心
    look_dir = world_center - cam_pos
    rot_quat = look_dir.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    # 诊断: 计算模型是否在相机前方
    to_model = world_center - cam_pos
    forward = cam.rotation_euler.to_matrix() @ Vector((0,0,-1))
    dot = to_model.normalized().dot(forward)
    print(f"{name}: cam={cam_pos}, dot={dot:.3f}")
    
    scene.render.filepath = os.path.join(out_dir, f"repair_screenshot_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Saved: {scene.render.filepath}")

print("All screenshots saved.")
