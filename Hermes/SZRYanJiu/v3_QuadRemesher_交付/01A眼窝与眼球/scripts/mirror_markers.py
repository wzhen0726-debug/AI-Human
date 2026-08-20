"""镜像R眼标记点到L眼: L(x,y,z) = (-R_x, R_y, R_z)."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

r_coll = bpy.data.collections.get("LM_R")
r_objs = sorted([o for o in r_coll.objects], key=lambda o: o.name)

# 清除旧L眼标记
l_coll = bpy.data.collections.get("LM_L")
if l_coll:
    for o in list(l_coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    l_coll = bpy.data.collections.new("LM_L")
    bpy.context.scene.collection.children.link(l_coll)

for o in r_objs:
    rx, ry, rz = o.location
    name = o.name.replace("_R", "_L")
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = 0.0025
    e.location = (-rx, ry, rz)  # 镜像x
    e.show_in_front = True
    e.color = (1.0, 0.3, 0.3, 1.0)  # 红色
    l_coll.objects.link(e)
    sw = e.constraints.new(type='SHRINKWRAP')
    sw.target = obj
    sw.shrinkwrap_type = 'NEAREST_SURFACE'
    sw.distance = 0.0

bpy.ops.wm.save_as_mainfile(filepath=MARKERS)
print(f"镜像完成: R眼{len(r_objs)}点 -> L眼")
print("saved")