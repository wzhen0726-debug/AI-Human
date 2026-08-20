"""纯诊断(不焊接): L眼4组+R眼残留"重复"顶点的精确距离与方向分类.
判定标准: 真重复=距离<0.02mm(应焊); 相邻环顶点=距离>0.05mm(不能焊,是碗底密集环)."""
import bpy, os, sys, json, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
me = obj.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
RAD = 0.030

for side in ("L", "R"):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < RAD]
    grid = {}
    for v in lv:
        k = (round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4))
        grid.setdefault(k, []).append(v)
    print(f"=== {side}眼 ===")
    for k, vs in grid.items():
        if len(vs) < 2: continue
        for a in range(len(vs)):
            for b in range(a+1, len(vs)):
                va, vb = vs[a], vs[b]
                d = (va.co - vb.co).length
                # 相对眼中心
                ra = Vector((va.co.x-c.x, va.co.y-c.y, va.co.z-c.z))
                rb = Vector((vb.co.x-c.x, vb.co.y-c.y, vb.co.z-c.z))
                rad_a = Vector((ra.x, 0, ra.z)); rad_b = Vector((rb.x, 0, rb.z))
                # 连线方向 vs 径向/切向
                delta = vb.co - va.co
                if rad_a.length > 1e-6:
                    radial_unit = rad_a / rad_a.length
                    tan = Vector((-radial_unit.z, 0, radial_unit.x))
                    dot_rad = abs(Vector((delta.x,0,delta.z)).normalized().dot(radial_unit)) if delta.xz.length > 1e-9 else 0
                    dot_tan = abs(Vector((delta.x,0,delta.z)).normalized().dot(tan)) if delta.xz.length > 1e-9 else 0
                    dy = delta.y
                else:
                    dot_rad = dot_tan = dy = 0
                verdict = "真重复(应焊)" if d < 0.00002 else ("相邻环顶点(勿焊)" if d > 0.00005 else "灰区")
                print(f"  对({va.index},{vb.index}) dist={d*1000:.4f}mm "
                      f"|ra|={rad_a.length*1000:.2f}mm |rb|={rad_b.length*1000:.2f}mm "
                      f"y_a={ra.y*1000:.2f}mm y_b={rb.y*1000:.2f}mm "
                      f"连线:径向分量={dot_rad:.2f} 切向分量={dot_tan:.2f} dy={dy*1000:.3f}mm "
                      f"→ {verdict}")
bm.free()
