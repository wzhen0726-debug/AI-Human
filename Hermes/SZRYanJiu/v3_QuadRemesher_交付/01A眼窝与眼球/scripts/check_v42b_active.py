"""快速验证: 当前01_2 blend的碗面avg_uv是否为v42b(亮度>0.40)"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]
tex_img = None
for mat in obj.data.materials:
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
W, H = tex_img.size; px = tex_img.pixels[:]
import bmesh, math
from mathutils import Vector
import json
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active
for side, center in [("L", cL), ("R", cR)]:
    n = 0; u_sum = v_sum = 0.0
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz < 0.012 and center.y - 0.002 < fc.y < center.y + 0.02:
            for l in f.loops:
                u_sum += l[uv_layer].uv.x; v_sum += l[uv_layer].uv.y; n += 1
            if n > 200: break
    if n:
        au, av = u_sum/n, v_sum/n
        x = min(max(int(au*W),0),W-1); y = min(max(int(av*H),0),H-1)
        i = (y*W+x)*4
        br = (px[i]+px[i+1]+px[i+2])/3
        print(f"{side} 碗面 avg_uv=({au:.4f},{av:.4f}) 采样亮度={br:.2f} {'✓v42b已生效' if br>0.40 else '✗仍是深色'} ({n}loops)")
bm.free()
