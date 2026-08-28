"""实测: ARP AI guess_markers 在本模型上的点位精度.
用arp_rig.py已验证的截图补丁(三视角Emission灰模) → guess_markers → dump 6+_loc位置,
与用户实测几何对照: 肩z≈1.454 / 腕x≈0.710 / 踝z≈0.101 / 骨盆z≈0.885 / 颈z≈1.473."""
import bpy, sys, os, math
from mathutils import Vector

TPL = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\A_半自动打点\07_arp_markers.blend"
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"

bpy.ops.wm.read_factory_settings(use_empty=True)
res = bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
print("启用ARP:", res)
bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH

# popup补丁(后台防崩)
for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        print("popup补丁OK")
        break

# 截图补丁: Emission灰模三视角 (复刻arp_rig.py已验证版本)
ars = None
for key, mod in sys.modules.items():
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

def screenshot_patched(self):
    scn = bpy.context.scene
    orig_engine = scn.render.engine
    ox, oy = scn.render.resolution_x, scn.render.resolution_y
    scn.render.engine = 'BLENDER_EEVEE'
    # 分辨率必须256: 官方_set_markers_from_keypoints用 ratio=dim/256 换算像素坐标
    # (推理exe输出与输入同空间; 512输入→512空间坐标÷256映射=2倍错位)
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
    margin = 1.35  # 固定留白1.35(原1.05指尖贴边→手肘检测失败)
    # 关键修复(2026-08-27): 官方_set_markers_from_keypoints靠self.larger_dim/midx/midz
    # 做像素→世界坐标换算, 不写回这些值则标记全落(0,0,0)且臂角零向量崩溃
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
# 加大臂展留白: 指尖原贴边导致手/肘检测失败 → ortho_scale放大
ars.AI_margin_override = 1.35

# 打开模板, 只留body (不改名body_temp — ARP内部会创建自己的body_temp副本,
# 之前改名导致同名冲突, 截图补丁误取原模型带黑衣物贴图 → AI识别失败)
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
        print(f"guess_markers 异常(可继续): {type(e).__name__}: {e}")

mk = [o for o in bpy.data.objects if o.name.endswith('_loc') or o.name.endswith('_loc_sym')]
print(f"AI标记数: {len(mk)}")
for o in sorted(mk, key=lambda x: x.name):
    p = o.matrix_world.translation
    print(f"AI_PT {o.name}: ({p.x:.3f},{p.y:.3f},{p.z:.3f})")
print("AI_TEST_DONE")
