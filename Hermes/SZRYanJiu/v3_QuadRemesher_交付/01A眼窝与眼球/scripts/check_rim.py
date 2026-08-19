"""测v41 rim半径-放宽条件版"""
import bpy, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
for side, center in [("L", cL), ("R", cR)]:
    # 放宽条件: dxz 10-25mm, y±3mm
    pts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        if 0.010 < dxz < 0.025 and abs(v.co.y - center.y) < 0.003:
            ang = math.atan2(v.co.z - center.z, v.co.x - center.x)
            pts.append((ang, dxz*1000))
    rim_r = {}; counts = {}
    for deg in range(0, 360, 10):
        a0, a1 = math.radians(deg-18), math.radians(deg+18)
        rs = [r for a, r in pts if a0 <= a < a1]
        if rs: rim_r[deg] = round(sum(rs)/len(rs), 1); counts[deg] = len(rs)
    vals = list(rim_r.values())
    print(f"{side}: {len(pts)}顶点, {len(vals)}/36角度覆盖")
    print(f"  范围{min(vals):.1f}-{max(vals):.1f}mm 波动{max(vals)-min(vals):.1f}mm avg={sum(vals)/len(vals):.1f}mm")
    for deg in sorted(rim_r):
        print(f"  {deg:>3}°: {rim_r[deg]:>5.1f}mm (n={counts[deg]})")
bm.free()