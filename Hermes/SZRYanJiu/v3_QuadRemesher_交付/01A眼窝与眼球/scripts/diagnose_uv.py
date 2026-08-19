"""v39 UV诊断: 检查ring0_uv捕获和avg_uv计算."""
import bpy, bmesh, json, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
uv_layer = bm.loops.layers.uv.active

for side, center in [("L", cL), ("R", cR)]:
    print(f"\n=== {side} UV诊断 ===")
    # 找ring0顶点
    rim_verts = [v for v in bm.verts
                 if 0.015 < (v.co-center).xz.length < 0.019
                 and abs(v.co.y - center.y) < 0.005]
    print(f"ring0顶点: {len(rim_verts)}")
    # 检查这些顶点的UV
    uvs = []
    for v in rim_verts:
        for loop in v.link_loops:
            uvs.append(loop[uv_layer].uv.copy())
            break
    if uvs:
        us = [uv.x for uv in uvs]; vs = [uv.y for uv in uvs]
        print(f"  UV范围: u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")
        print(f"  UV中心: ({sum(us)/len(us):.4f}, {sum(vs)/len(vs):.4f})")
        # 检查是否均匀
        avg_u = sum(us)/len(us); avg_v = sum(vs)/len(vs)
        same = sum(1 for uv in uvs if abs(uv.x-avg_u)<0.001 and abs(uv.y-avg_v)<0.001)
        print(f"  均匀占比: {same}/{len(uvs)} ({same/len(uvs)*100:.1f}%)")
bm.free()
