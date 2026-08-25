"""肩部打点参考图 v2: 渲染肩部特写(线框+实体), 用PIL在图上画标注圈+文字.
比3D红球可靠(3D球会被身体遮挡), PIL直接画在像素上100%可见."""
import bpy, os, json
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
MARKERS = os.path.join(DELIVERY, "05骨骼绑定", "A_半自动打点", "06_rig_markers.blend")
OUT_DIR = os.path.join(DELIVERY, "05骨骼绑定", "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

joints = json.load(open(os.path.join(DELIVERY, "05骨骼绑定", "A_半自动打点", "joints_measured.json"), encoding="utf-8"))
sh_r = np.array(joints["Shoulder_R"])
sh_l = np.array([-sh_r[0], sh_r[1], sh_r[2]])

bpy.ops.wm.open_mainfile(filepath=MARKERS)
body = max([o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()],
           key=lambda o: len(o.data.vertices))
body.display_type = 'SOLID'

# 渲染设置(聚焦肩颈)
s = bpy.context.scene
s.render.engine = 'BLENDER_EEVEE'
s.render.resolution_x = 1000; s.render.resolution_y = 900
for nm in ("Key", "Fill", "Rim"):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o, do_unlink=True)
for name, loc_rel, energy in [("Key", Vector((0.4, -1.5, 1.0)), 40),
                              ("Fill", Vector((-0.8, -0.5, 0.3)), 15),
                              ("Rim", Vector((0, 1.5, 0.8)), 25)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.5
    lo = bpy.data.objects.new(name, ld); lo.location = Vector((0, 0, 1.3)) + loc_rel
    lo.rotation_euler = (Vector((0, 0, 1.3)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
    s.collection.objects.link(lo)
if s.world is None: s.world = bpy.data.worlds.new("World")
s.world.use_nodes = True
bg = s.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.15, 0.15, 0.17, 1.0); bg.inputs['Strength'].default_value = 0.5

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene: s.collection.objects.link(cam)
s.camera = cam
cam.data.lens = 85
shoulder_center = Vector((0, 0, 1.44))
cam.location = shoulder_center + Vector((0, -1.3, 0.05))
cam.rotation_euler = (shoulder_center - cam.location).to_track_quat('-Z', 'Y').to_euler()

# 渲染底图
tmp_png = os.path.join(OUT_DIR, "_tmp_shoulder.png")
s.render.filepath = tmp_png
bpy.ops.render.render(write_still=True)

# 肩点世界→像素投影
def world_to_px(p):
    vec = Vector(tuple(p))
    # 世界→相机坐标
    cam_mat = cam.matrix_world.inverted()
    v_cam = cam_mat @ vec
    if v_cam.z > 0:  # 相机看向-z
        return None
    fov_y = 2 * np.arctan(cam.data.sensor_height / 2 / cam.data.lens) if cam.data.sensor_height else np.radians(40)
    # 用Blender投影更准
    co = bpy.context.scene.camera.matrix_world.inverted() @ vec
    W, H = s.render.resolution_x, s.render.resolution_y
    # 透视投影
    fx = (W / 2) / np.tan(np.radians(cam.data.angle) / 2)
    px = W/2 + fx * co.x / (-co.z)
    py = H/2 - fx * co.y / (-co.z)
    return (int(px), int(py))

# 用Blender原生投影
for nm in ("肩标记_R", "肩标记_L"):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o, do_unlink=True)

def project_point(world_pt):
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(s, cam, Vector(tuple(world_pt)))
    W, H = s.render.resolution_x, s.render.resolution_y
    return (int(co.x * W), int((1 - co.y) * H))

pr = project_point(sh_r)
pl = project_point(sh_l)
print(f"肩R像素: {pr}  肩L像素: {pl}")

# PIL画标注
img = Image.open(tmp_png).convert("RGB")
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
    font_s = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 18)
except:
    font = ImageFont.load_default()
    font_s = font

def mark(px, label, label_pos="right"):
    if px is None: return
    x, y = px
    r = 30
    # 红圈(双圈加粗)
    for rr in range(r-2, r+3):
        draw.ellipse([x-rr, y-rr, x+rr, y+rr], outline=(255, 40, 40), width=1)
    draw.ellipse([x-4, y-4, x+4, y+4], fill=(255, 40, 40))
    # 引线+文字
    if label_pos == "right":
        lx1, ly1 = x + r + 5, y
        lx2, ly2 = x + r + 60, y - 40
    else:
        lx1, ly1 = x - r - 5, y
        lx2, ly2 = x - r - 60, y - 40
    draw.line([lx1, ly1, lx2, ly2], fill=(255, 40, 40), width=3)
    tx = lx2 + (8 if label_pos == "right" else -8)
    draw.text((tx, ly2 - 12), label, fill=(255, 255, 80), font=font, anchor="lm" if label_pos=="right" else "rm")

mark(pr, "肩关节点(肱骨头)", "right")
mark(pl, "肩关节点(肱骨头)", "left")

# 底部说明条
txt = "红点=肩关节旋转中心(肱骨头, 肩峰正下方1-2cm, 三角肌深层)  不是三角肌中点, 也不是锁骨末端"
draw.rectangle([0, img.height-60, img.width, img.height], fill=(0,0,0))
draw.text((img.width//2, img.height-30), txt, fill=(255,255,255), font=font_s, anchor="mm")

out = os.path.join(OUT_DIR, "肩部打点参考_正面标注版.png")
img.save(out)
os.remove(tmp_png)
print(f"已保存: {out}")
print("SHOULDER_REF_V2_DONE")
