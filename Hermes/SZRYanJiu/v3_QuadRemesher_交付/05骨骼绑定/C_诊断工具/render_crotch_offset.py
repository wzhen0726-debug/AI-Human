"""渲染会阴点偏移对比图: 正面视图+中线+红球(用户点)+绿球(正确位置)."""
import bpy
from mathutils import Vector

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\screenshots\会阴点偏移对比_0826.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
scn = bpy.context.scene

# 1. 中线参考线: 从颈根到脚踝的垂直线 (用细圆柱)
line_verts = [(0.0, 0.0, 1.6), (0.0, 0.0, 0.05)]
import bmesh
bm = bmesh.new()
v0 = bm.verts.new((0.0, 0.0, 1.6))
v1 = bm.verts.new((0.0, 0.0, 0.05))
bm.verts.ensure_lookup_table()
edge = bm.edges.new((v0, v1))
line_mesh = bpy.data.meshes.new("_midline")
bm.to_mesh(line_mesh)
bm.free()
line_obj = bpy.data.objects.new("_midline", line_mesh)
scn.collection.objects.link(line_obj)
line_mat = bpy.data.materials.new("_midline_mat")
line_mat.diffuse_color = (0.0, 1.0, 0.0, 1.0)
line_obj.data.materials.append(line_mat)
line_obj.show_in_front = True

# 2. 找会阴点位置
crotch = None
for o in bpy.data.objects:
    if o.name.startswith("LM_03"):
        crotch = o.matrix_world.translation.copy()
        break

# 3. 红球: 用户打的点
# 4. 绿球: 同高度中线位置 (x=0)
ball_mesh = bpy.data.meshes.new("_vball")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.03)
bm.to_mesh(ball_mesh)
bm.free()

for pos, color, name in [
    (crotch, (1.0, 0.0, 0.0, 1.0), "_ball_user"),
    (Vector((0.0, crotch.y, crotch.z)), (0.0, 1.0, 0.0, 1.0), "_ball_correct"),
]:
    ball = bpy.data.objects.new(name, ball_mesh)
    ball.location = pos
    mat = bpy.data.materials.new(name + "_mat")
    mat.diffuse_color = color
    ball.data.materials.append(mat)
    ball.show_in_front = True
    scn.collection.objects.link(ball)

# 5. 文字: 偏移量说明
cu = bpy.data.curves.new("_note", 'FONT')
cu.body = f"红=你打的点  绿=中线  偏了{abs(crotch.x)*1000:.0f}mm"
cu.size = 0.05
txt = bpy.data.objects.new("_note", cu)
txt.location = (0.35, -1.5, 0.85)
txt.rotation_euler = (1.5708, 0.0, 0.0)
scn.collection.objects.link(txt)

# 6. 相机: 正面, 对准胯部
cam = bpy.data.cameras.new("_cam")
cam.type = 'ORTHO'
cam.ortho_scale = 1.4
cam_obj = bpy.data.objects.new("_cam", cam)
cam_obj.location = (0.0, -2.0, 0.75)
cam_obj.rotation_euler = (1.5708, 0.0, 0.0)
scn.collection.objects.link(cam_obj)
scn.camera = cam_obj

scn.render.engine = 'BLENDER_WORKBENCH'
scn.render.resolution_x = 800
scn.render.resolution_y = 1000
scn.render.image_settings.file_format = 'PNG'
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)

# 清理临时对象
for name in ["_midline", "_ball_user", "_ball_correct", "_note"]:
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

print(f"会阴点: ({crotch.x:.3f}, {crotch.y:.3f}, {crotch.z:.3f})")
print(f"偏移: {crotch.x*1000:.0f}mm (X方向)")
print("RENDER_CROTCH_DONE")
