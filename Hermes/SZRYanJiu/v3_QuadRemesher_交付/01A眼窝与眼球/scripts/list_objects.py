"""列出OUT_BLEND内所有对象及网格统计, 定位眼窝对象."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
scene = bpy.context.scene
print("=== objects in", OUT_BLEND, "===")
for o in scene.objects:
    if o.type == 'MESH':
        me = o.data
        print(f"MESH  name={o.name!r} verts={len(me.vertices)} faces={len(me.polygons)}")
        bbox = [o.matrix_world @ v.co for v in me.vertices[:1]]
        print(f"      sample world co: {bbox[0][:]}")
    else:
        print(f"{o.type:6} name={o.name!r}")
print("=== mesh objects in bpy.data (可能未链接到场景) ===")
for m in bpy.data.meshes:
    print(f"data.mesh name={m.name!r} users={m.users} verts={len(m.vertices)}")
