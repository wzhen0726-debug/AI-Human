"""定位非流形边: 输出每条非流形边的坐标和相邻面数."""
import bpy, bmesh, json, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

non_manifold = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"非流形边: {len(non_manifold)}")
for e in non_manifold:
    v0, v1 = e.verts
    mx = (v0.co.x+v1.co.x)/2; my=(v0.co.y+v1.co.y)/2; mz=(v0.co.z+v1.co.z)/2
    dl = (Vector((mx,my,mz))-cL).length; dr = (Vector((mx,my,mz))-cR).length
    nf = len(e.link_faces)
    print(f"  edge @({mx*1000:.2f},{my*1000:.2f},{mz*1000:.2f})mm, {nf}面, 距L={dl*1000:.1f}mm 距R={dr*1000:.1f}mm")
    # 面类型
    for f in e.link_faces:
        fc = f.calc_center_median()
        print(f"    面: {len(f.verts)}边形, 中心({fc.x*1000:.1f},{fc.y*1000:.1f},{fc.z*1000:.1f})mm")

bm.free()
