"""diagnose_eyeball_material.py - 查01_2眼球材质: 贴图是否加载/UV是否有效
vision报"眼球纯平灰白, 无虹膜无瞳孔"
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend"))
eyes = [o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' in o.name]
for o in eyes:
    print(f"=== {o.name} loc={tuple(round(v,4) for v in o.location)} ===")
    me = o.data
    print(f"  verts={len(me.vertices)} faces={len(me.polygons)}")
    print(f"  uv_layers={[l.name for l in me.uv_layers]}")
    for l in me.uv_layers:
        l.active = True
        uvs = [d.uv for d in me.uv_layers.active.data]
        us = [u.x for u in uvs]; vs = [u.y for u in uvs]
        print(f"  uv '{l.name}': u=[{min(us):.3f},{max(us):.3f}] v=[{min(vs):.3f},{max(vs):.3f}]")
    for mi, mat in enumerate(o.data.materials):
        print(f"  material[{mi}]: {mat.name if mat else None}")
        if not mat or not mat.use_nodes: continue
        for n in mat.node_tree.nodes:
            info = f"type={n.type}"
            if n.type == 'TEX_IMAGE' and n.image:
                info += f" img={n.image.name} {n.image.size[0]}x{n.image.size[1]} users={n.image.users} packed={n.image.packed_file is not None}"
            elif n.type == 'BSDF_PRINCIPLED':
                bc = n.inputs['Base Color']
                info += f" base_color={tuple(round(v,3) for v in bc.default_value)} linked={bc.is_linked}"
            print(f"    node: {info}")
        for link in mat.node_tree.links:
            print(f"    link: {link.from_node.name}.{link.from_socket.name} -> {link.to_node.name}.{link.to_socket.name}")
print("MAT DIAG DONE")
