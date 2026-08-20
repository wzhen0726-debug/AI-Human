"""打印输入高模所有材质的贴图路径, 找到眼睛/脸部贴图."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
for m in bpy.data.materials:
    if not m.use_nodes: continue
    imgs = set()
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image:
            imgs.add(n.image.filepath)
    if imgs:
        print(f"[{m.name}]")
        for p in sorted(imgs):
            print(f"   {p}")
print("DONE")
