"""渲染打点模板正面视图 v2: Workbench(后台截图标准)+临时球体显示标记点."""
import bpy, math
from mathutils import Vector

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\screenshots\模板正面验证2_0825.png"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
scn = bpy.context.scene

# 临时球体显示标记点位置(空对象不渲染)
dg = bpy.context.evaluated_depsgraph_get()
ball_mesh = bpy.data.meshes.new("_vball")
import bmesh
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.035)
bm.to_mesh(ball_mesh)
bm.free()

colors = {"M": (1.0, 0.85, 0.1, 1.0), "R": (1.0, 0.25, 0.25, 1.0), "L": (0.35, 0.5, 1.0, 1.0)}
for o in bpy.data.objects:
    if not o.name.startswith("LM_"):
        continue
    ev = o.evaluated_get(dg).matrix_world.translation
    tag = "M" if o.name.startswith("LM_0") and int(o.name.split("_")[1]) <= 3 else ("R" if "_R" in o.name else "L")
    mat = bpy.data.materials.new(f"_vball_{o.name}")
    mat.diffuse_color = colors[tag]
    b = bpy.data.objects.new(f"_vball_{o.name}", ball_mesh)
    b.data.materials.append(mat)
    b.location = ev
    scn.collection.objects.link(b)

# 文字牌加亮色材质(默认文字是黑色,暗背景下看不见)
txtmat = bpy.data.materials.new("_vtxt")
txtmat.diffuse_color = (0.1, 0.9, 0.3, 1.0)
for o in bpy.data.objects:
    if o.type == 'FONT':
        o.data.materials.clear()
        o.data.materials.append(txtmat)

# 相机: 正视(从−Y看向+Y), 与模板视口一致
cam_data = bpy.data.cameras.new("_验证相机")
cam = bpy.data.objects.new("_验证相机", cam_data)
scn.collection.objects.link(cam)
cam.location = (0, -3.2, 0.95)
cam.rotation_euler = (math.pi / 2, 0, 0)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 3.4
scn.camera = cam

# Workbench渲染(后台截图标准: 无光照依赖,颜色清晰)
scn.render.engine = 'BLENDER_WORKBENCH'
scn.render.resolution_x = 1000
scn.render.resolution_y = 1000
scn.render.image_settings.file_format = 'PNG'
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDER2_DONE", OUT)
