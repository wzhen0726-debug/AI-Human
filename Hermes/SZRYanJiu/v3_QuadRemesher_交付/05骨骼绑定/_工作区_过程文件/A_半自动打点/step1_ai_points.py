"""第1步: 跑ARP AI guess_markers, 点位存JSON (复用ai_guess_test.py已验证补丁)."""
import bpy, sys, os, math, json
from mathutils import Vector

TPL = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\A_半自动打点\07_arp_markers.blend"
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\logs\ai_points.json"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH

for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break

ars = None
for key, mod in sys.modules.items():
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

# 截图补丁(已验证版本: 256分辨率+灰模Emission+self写回)
def screenshot_patched(self):
    scn = bpy.context.scene
    orig_engine = scn.render.engine
    ox, oy = scn.render.resolution_x, scn.render.resolution_y
    scn.render.engine = 'BLENDER_EEVEE'
    scn.render.resolution_x = 256
    scn.render.resolution_y = 256
    scn.render.image_settings.file_format = 'JPEG'
    body_temp = bpy.data.objects.get('body_temp')
    if not body_temp:
        print("ERROR: body_temp缺失")
        return
    mat = bpy.data.materials.new("arp_gray")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes["Principled BSDF"].inputs["Base Color"].default_value = (0, 0, 0, 1.0)
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    mat.node_tree.links.new(emit.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    body_temp.data.materials.clear()
    body_temp.data.materials.append(mat)
    self.front_samples_rot = [0.0]
    if scn.world is None:
        scn.world = bpy.data.worlds.new("arp_bg")
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    corners = [body_temp.matrix_world @ Vector(c) for c in body_temp.bound_box]
    x1, x2 = corners[0][0], corners[4][0]
    y1, y2 = corners[0][1], corners[6][1]
    z1, z2 = corners[0][2], corners[2][2]
    dx, dy, dz = abs(x2-x1), abs(y2-y1), abs(z2-z1)
    mx, my, mz = (x1+x2)/2, (y1+y2)/2, (z1+z2)/2
    lower_y, gx, gz = min(y1, y2), max(x1, x2), max(z1, z2)
    l1, l2, l3 = max(dx, dz), max(dy, dz), max(dy, dx)
    margin = 1.35
    self.larger_dim, self.larger_dimy, self.larger_dimtop = l1, l2, l3
    self.midx, self.midy, self.midz = mx, my, mz
    self.margin = margin
    cam_data = bpy.data.cameras.new("arp_cam_char")
    cam_data.type = 'ORTHO'
    cam_data.clip_end = 50000
    cam_obj = bpy.data.objects.new("arp_cam_char", cam_data)
    scn.collection.objects.link(cam_obj)
    scn.camera = cam_obj
    inf = self.inf_path
    def rv(name, loc, rot, ortho):
        cam_obj.location, cam_obj.rotation_euler = loc, rot
        cam_obj.data.ortho_scale = ortho
        scn.render.filepath = os.path.join(inf, name)
        bpy.ops.render.render(write_still=True)
        print(f"  截图 {name}")
    rv("front1.jpg", (mx, lower_y - dy*10, mz), (math.pi/2, 0, 0), l1*margin)
    rv("char_side.jpg", (gx + dx*10, my, mz), (math.pi/2, 0, math.pi/2), l2*margin)
    rv("char_top.jpg", (mx, my, gz + dz*10), (0, 0, 0), l3*margin)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    scn.render.engine, scn.render.resolution_x, scn.render.resolution_y = orig_engine, ox, oy

if ars:
    ars._screenshot_char = screenshot_patched
    print("截图补丁OK")

# 打开模板只留body(不改名, 避免与ARP内部body_temp撞名)
bpy.ops.wm.open_mainfile(filepath=TPL)
for o in list(bpy.data.objects):
    if o.name != BODY:
        bpy.data.objects.remove(o, do_unlink=True)
body = bpy.data.objects[BODY]
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body

bpy.context.window.screen = bpy.data.screens['Layout']
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')

with bpy.context.temp_override(area=area, region=region):
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    bpy.context.scene.arp_smart_AI_body_samples = 1
    try:
        bpy.ops.arp.guess_markers('EXEC_DEFAULT')
        print("guess_markers 完整成功")
    except Exception as e:
        print(f"guess_markers 异常: {type(e).__name__}: {e}")

# 存JSON
pts = {}
for o in bpy.data.objects:
    if o.name.endswith('_loc') or o.name.endswith('_loc_sym'):
        p = o.matrix_world.translation
        pts[o.name] = [round(p.x, 4), round(p.y, 4), round(p.z, 4)]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(pts, f, ensure_ascii=False, indent=1)
print(f"AI_PT_COUNT {len(pts)}")
for k in sorted(pts): print(f"AI_PT {k}: {pts[k]}")
print("STEP1_DONE")
