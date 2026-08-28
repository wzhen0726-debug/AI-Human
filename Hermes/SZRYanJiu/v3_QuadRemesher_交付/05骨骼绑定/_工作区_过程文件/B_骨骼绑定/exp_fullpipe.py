"""决定性实验: 同一会话内完整官方流程 guess_markers → go_detect.
对比我的分步流程(自建模板→go_detect)结果 — 若此实验骨架正确,
根因=自建模板缺少guess_markers建立的某些状态/属性."""
import bpy, sys, os, math
from mathutils import Vector

TPL = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\A_半自动打点\07_arp_markers.blend"
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"
BODY = "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\_工作区_过程文件\B_骨骼绑定\09_arp_rig_fullpipe.blend"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
bpy.context.preferences.addons['auto_rig_pro-master'].preferences.ai_presets_path = AI_PATH

for key, mod in list(sys.modules.items()):
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        mod.display_popup_message = lambda m, h=' ', i='': print(f"[ARP {h}] {m}")
        break

ars = None
for key, mod in list(sys.modules.items()):
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

# 已验证的截图补丁 (256分辨率+灰模+self写回)
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
    rv("front1.jpg", (mx, lower_y - dy*10, mz), (math.pi/2, 0, 0), l1*margin)
    rv("char_side.jpg", (gx + dx*10, my, mz), (math.pi/2, 0, math.pi/2), l2*margin)
    rv("char_top.jpg", (mx, my, gz + dz*10), (0, 0, 0), l3*margin)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    scn.render.engine, scn.render.resolution_x, scn.render.resolution_y = orig_engine, ox, oy

if ars:
    ars._screenshot_char = screenshot_patched

# 打开模板只留body
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
scn = bpy.context.scene

# ===== 完整官方流程: guess_markers → go_detect =====
with bpy.context.temp_override(area=area, region=region):
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    scn.arp_smart_AI_body_samples = 1
    try:
        bpy.ops.arp.guess_markers('EXEC_DEFAULT')
        print("guess_markers OK")
    except Exception as e:
        print(f"guess_markers异常: {type(e).__name__}: {e}")

    # 打印guess后的标记(含父级/属性, 对比自建模板的差异)
    print("=== guess后标记对象状态 ===")
    for o in sorted(bpy.data.objects, key=lambda x: x.name):
        if o.name.endswith('_loc') or o.name.endswith('_loc_sym'):
            parent = o.parent.name if o.parent else "无父级"
            props = {k: v for k, v in o.items() if not k.startswith('_')}
            print(f"{o.name}: loc=({o.location.x:.3f},{o.location.y:.3f},{o.location.z:.3f}) 父={parent} 属性={props}")

    # 直接go_detect (不中断不保存)
    scn.arp_smart_depth = False
    scn.arp_smart_fingers_engine = 'LEGACY'
    try:
        bpy.ops.id.go_detect('EXEC_DEFAULT')
        print("go_detect OK")
    except Exception as e:
        print(f"go_detect异常: {type(e).__name__}: {e}")

# 验证骨架
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm:
    mw = arm.matrix_world
    def bh(n):
        b = arm.data.bones.get(n)
        return (mw @ b.head_local) if b else None
    sh, ha = bh("shoulder.l"), bh("hand.l")
    print(f"\n=== 实验结果: 骨架{len(arm.data.bones)}骨 ===")
    if sh and ha:
        print(f"shoulder.l: ({sh.x:.3f},{sh.y:.3f},{sh.z:.3f})")
        print(f"hand.l: ({ha.x:.3f},{ha.y:.3f},{ha.z:.3f})")
        print(f"标记参考: shoulder=(0.229,0.048,1.435) hand=(0.715,0.019,1.435)")
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
else:
    print("ERROR: 无骨架")
print("FULLPIPE_DONE")
