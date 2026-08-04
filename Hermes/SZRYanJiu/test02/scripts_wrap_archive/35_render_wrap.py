import bpy, os, sys, math
from mathutils import Vector, Matrix
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
WRAPPED_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_v2.blend")
OUT_DIR = os.path.join(ROOT, "output", "verification")
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=WRAPPED_BLEND)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"网格数: {len(meshes)}")
for m in meshes:
    zs = [v.co.z for v in m.data.vertices]
    xs = [v.co.x for v in m.data.vertices]
    ys = [v.co.y for v in m.data.vertices]
    print(f"  {m.name}: {len(m.data.vertices)} verts, X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# 渲染front/left/top
import math
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.film_transparent = False
bpy.context.scene.world.color = (0.9, 0.9, 0.9)

bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
bpy.context.active_object.data.energy = 5.0

bpy.ops.object.camera_add()
cam = bpy.context.active_object
bpy.context.scene.camera = cam

# 找Tripo和MetaHuman
tripo = None
mh = None
for m in meshes:
    if 'Tripo' in m.name or 'HighPoly' in m.name:
        tripo = m
    elif 'Body' in m.name or 'MetaHuman' in m.name:
        mh = m

# 渲染MetaHuman包裹结果
for name, direction in [('mh_front', (0,-2,0)), ('mh_left', (-2,0,0)), ('mh_top', (0,0,2))]:
    cam.location = Vector((0, 0.9, 0.8)) + Vector(direction)
    look = Vector((0, 0.9, 0.8)) - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"wrap_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  渲染: wrap_{name}.png")

print("DONE")
