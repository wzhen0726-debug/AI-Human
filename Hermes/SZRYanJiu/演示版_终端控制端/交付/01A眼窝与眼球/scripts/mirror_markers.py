"""镜像R眼标记点到L眼: L(x,y,z) = (-R_x, R_y, R_z).

2026-09-08 v3同步: 继承R眼的尺寸/颜色/自定义属性(分组/序号), 并为L眼建顺序线
(驱动器绑定L标记, 放LM_VIS集合). 曲线对象绝不进LM_R/LM_L(会被read当成标记点)."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)

r_coll = bpy.data.collections.get("LM_R")
r_objs = sorted([o for o in r_coll.objects if o.type == 'EMPTY'], key=lambda o: o.name)

# 清除旧L眼标记 + 旧L顺序线
l_coll = bpy.data.collections.get("LM_L")
if l_coll:
    for o in list(l_coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    l_coll = bpy.data.collections.new("LM_L")
    bpy.context.scene.collection.children.link(l_coll)
vis = bpy.data.collections.get("LM_VIS")
if vis is None:
    vis = bpy.data.collections.new("LM_VIS")
    bpy.context.scene.collection.children.link(vis)
old_c = bpy.data.objects.get("眼裂顺序线_L")
if old_c:
    bpy.data.objects.remove(old_c, do_unlink=True)

l_objs = []
for o in r_objs:
    rx, ry, rz = o.location
    name = o.name.replace("_R", "_L")
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = o.empty_display_size   # 继承尺寸(眼角1.5×)
    e.location = (-rx, ry, rz)  # 镜像x
    e.show_in_front = True
    e.color = o.color           # 继承分组颜色(眼角黄/上睑青/下睑橙)
    for k in ("lid_group", "order_index"):
        if k in o: e[k] = o[k]
    l_coll.objects.link(e)
    l_objs.append(e)

# L眼顺序线(闭合样条+驱动器)
cu = bpy.data.curves.new("眼裂顺序线_L", type='CURVE')
cu.dimensions = '3D'
sp = cu.splines.new('POLY')
sp.points.add(len(l_objs) - 1)
sp.use_cyclic_u = True
for i, e in enumerate(l_objs):
    sp.points[i].co = (*e.location, 1.0)
cu_obj = bpy.data.objects.new("眼裂顺序线_L", cu)
cu_obj.show_in_front = True
cu_obj.hide_select = True
cu_obj.color = (1.0, 1.0, 1.0, 1.0)
vis.objects.link(cu_obj)
n_drv = 0
for i, e in enumerate(l_objs):
    for axis, idx in (("x",0),("y",1),("z",2)):
        drv = sp.points[i].driver_add("co", idx)
        drv.driver.type = 'SCRIPTED'
        var = drv.driver.variables.new()
        var.type = 'TRANSFORMS'
        var.targets[0].id = e
        var.targets[0].transform_type = 'LOC_' + axis.upper()
        var.targets[0].transform_space = 'WORLD_SPACE'
        drv.driver.expression = "var"
        n_drv += 1

bpy.ops.wm.save_as_mainfile(filepath=MARKERS)
print(f"镜像完成: R眼{len(r_objs)}点 -> L眼{len(l_objs)}点 (尺寸/颜色/分组属性已继承)")
print(f"L眼顺序线: {len(l_objs)}点闭合样条 + {n_drv}驱动器")
print("saved")
