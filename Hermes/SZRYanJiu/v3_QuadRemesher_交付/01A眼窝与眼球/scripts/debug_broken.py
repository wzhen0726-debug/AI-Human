
import bpy, numpy as np, bmesh, json
from mathutils import Vector
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=SOCKET)
d = json.load(open(EYELID, encoding="utf-8"))
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
mesh = head.data

# 检测眼窝区破面: 非流形边(>2面共享) + 退化面
bpy.context.view_layer.objects.active = head
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
c = np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
def near(fc): return np.hypot(fc.x-c[0], fc.z-c[2])<0.020
# 非流形边(>2面)在眼窝附近
nonmanifold=[e for e in bm.edges if len(e.link_faces)>2 and near(e.verts[0].co)]
# 退化面(面积近0)在眼窝附近
degen=[f for f in bm.faces if near(f.calc_center_median()) and f.calc_area()<1e-10]
# 零面积/重叠: 检查碗内面数
cup_faces=[f for f in bm.faces if near(f.calc_center_median())]
bpy.ops.object.mode_set(mode='OBJECT')
print(f"左眼窝区: 面数={len(cup_faces)} 非流形边={len(nonmanifold)} 退化面={len(degen)}")

# 渲染眼窝特写
scene = bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'; scene.render.resolution_x=900; scene.render.resolution_y=900
scene.display.shading.light='STUDIO'; scene.display.shading.show_cavity=True
cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: scene.collection.objects.link(cam)
scene.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=0.06
cv=Vector(c)
cam.location=Vector((cv.x, cv.y-0.15, cv.z)); cam.rotation_euler=(cv-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\socket_closeup.png"
bpy.ops.render.render(write_still=True)
print("saved socket_closeup")
