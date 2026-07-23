"""渲染高模修复后的模型截图 — 正面+侧面+3/4视角"""
import bpy, sys, os, math

obj = None
for o in bpy.data.objects:
    if o.type == 'MESH':
        obj = o
        break

if not obj:
    print("ERROR: No mesh")
    sys.exit(1)

# 获取模型尺寸
xs = [v.co.x for v in obj.data.vertices]
ys = [v.co.y for v in obj.data.vertices]
zs = [v.co.z for v in obj.data.vertices]
mn = (min(xs), min(ys), min(zs))
mx = (max(xs), max(ys), max(zs))
dims = (mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2])
center = ((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2)

# 设置渲染参数
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = 'WORLD'
scene.display.shading.curvature_ridge_factor = 1.5
scene.display.shading.curvature_valley_factor = 1.0

# 确保有相机
cam = bpy.data.objects.get("Camera")
if not cam:
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    scene.camera = cam

# 输出目录
out_dir = os.path.dirname(bpy.data.filepath)
angles = [
    ("front", 0, 0),      # 正面
    ("side", math.pi/2, 0),  # 侧面
    ("three_quarter", math.pi/4, math.pi/6),  # 3/4视角
]

for name, rot_y, rot_z in angles:
    # 相机距离 = 模型最大维度 * 1.5（更紧凑的取景）
    dist = max(dims) * 1.5
    
    # 相机位置（绕Y轴旋转，绕Z轴抬升）
    cam_x = center[0] + dist * math.sin(rot_y) * math.cos(rot_z)
    cam_y = center[1] - dist * math.cos(rot_y) * math.cos(rot_z)
    cam_z = center[2] + dist * math.sin(rot_z)
    
    cam.location = (cam_x, cam_y, cam_z)
    
    # 相机看向模型中心
    from mathutils import Vector
    look_dir = Vector((center[0] - cam_x, center[1] - cam_y, center[2] - cam_z))
    rot_quat = look_dir.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    scene.render.filepath = os.path.join(out_dir, f"repair_screenshot_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Saved: {scene.render.filepath}")

print("All screenshots saved.")
