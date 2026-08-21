"""只重渲染(不重建): 打开01_2_eyeball_placed.blend, 正面平视+双眼完整入镜, 供验收."""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1000; scene.render.resolution_y = 800

eyes = [o for o in bpy.data.objects if o.name.startswith("Eye002")]
fc = sum((o.location for o in eyes), Vector((0, 0, 0))) / 2

# 清旧灯, 三灯柔光
for nm in ("Key", "Fill", "Rim"):
    o = bpy.data.objects.get(nm)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
for name, loc_rel, energy in [("Key", Vector((0.1, -0.6, 0.35)), 40),
                              ("Fill", Vector((0.5, -0.2, 0.1)), 15),
                              ("Rim", Vector((0, 0.6, 0.3)), 20)]:
    ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 0.6
    lo = bpy.data.objects.new(name, ld); lo.location = fc + loc_rel
    lo.rotation_euler = (fc - lo.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(lo)
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.62, 0.62, 0.64, 1.0); bg.inputs['Strength'].default_value = 0.6

cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
if not cam.users_scene:
    scene.collection.objects.link(cam)
scene.camera = cam

# 正面平视: 相机与双眼中心同高, 距离250mm, 50mm镜头 → 视场宽约160mm(双眼完整)
for tag, dist, lens in [("front", 0.25, 50), ("close", 0.15, 50)]:
    cam.data.lens = lens
    cam.location = Vector((fc.x, fc.y - dist, fc.z + 0.004))  # 微抬4mm避免仰视畸变
    cam.rotation_euler = (fc - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(SHOT_DIR, f"v3c_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: v3c_{tag}.png cam={tuple(round(v,3) for v in cam.location)} lens={lens}")
print("done")
