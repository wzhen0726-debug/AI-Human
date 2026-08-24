"""rim锐化前后对比渲染: 打开锐化版+原低模, 并排渲染rim特写."""
import bpy, os
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
OUT = os.path.join(DELIVERY, "02QuadRemesher拓扑", "screenshots")

def render(blend, tag):
    bpy.ops.wm.open_mainfile(filepath=blend)
    head = max([o for o in bpy.data.objects if o.type == 'MESH'],
               key=lambda o: len(o.data.vertices))
    # 找眼中心
    import json
    cont = json.load(open(os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))
    fc = Vector(cont["L"]["center"]) if "L" in tag else Vector(cont["R"]["center"])
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x = 800; s.render.resolution_y = 600
    for name, loc_rel, energy in [("Key", Vector((0.1, -0.6, 0.35)), 40),
                                  ("Fill", Vector((0.5, -0.2, 0.1)), 15),
                                  ("Rim", Vector((0, 0.6, 0.3)), 20)]:
        ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 0.6
        lo = bpy.data.objects.new(name, ld); lo.location = fc + loc_rel
        lo.rotation_euler = (fc - lo.location).to_track_quat('-Z', 'Y').to_euler()
        s.collection.objects.link(lo)
    if s.world is None: s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bg = s.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.62, 0.62, 0.64, 1.0); bg.inputs['Strength'].default_value = 0.6
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene: s.collection.objects.link(cam)
    s.camera = cam
    cam.data.lens = 85
    cam.location = Vector((fc.x, fc.y - 0.12, fc.z + 0.002))
    cam.rotation_euler = (fc - cam.location).to_track_quat('-Z', 'Y').to_euler()
    s.render.filepath = os.path.join(OUT, f"rim_compare_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print(f"shot: rim_compare_{tag}.png")

render(os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_ring.blend"), "L_orig")
render(os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_ring.blend"), "L_ring")
print("COMPARE_DONE")
