"""定量验证碗底极点扇完好: R眼碗底极点应连74个三角面(M=74), L眼应84个(M=84).
同时统计末环顶点数(径向<1.5mm内, 排除极点)."""
import bpy, os, sys, json, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()
ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))

for side, expect_M in (("L", 84), ("R", 74)):
    c = Vector(ddfa[side]["center_3d"])
    # 极点 = 眼中心径向<0.5mm且深度最大的顶点(碗底中心点)
    cand = [v for v in bm.verts if Vector((v.co.x-c.x, 0, v.co.z-c.z)).length < 0.0005]
    if not cand:
        print(f"{side}眼: 未找到碗底极点!!"); continue
    pole = max(cand, key=lambda v: v.co.y)  # 碗底=最深处(y最大,模型朝-y为前)
    # 极点连接的三角面
    tri = [f for f in pole.link_faces if len(f.verts) == 3]
    quad = [f for f in pole.link_faces if len(f.verts) == 4]
    # 末环顶点: 径向0.5~2mm
    last_ring = [v for v in bm.verts if 0.0005 < Vector((v.co.x-c.x,0,v.co.z-c.z)).length < 0.002]
    print(f"{side}眼: 极点idx={pole.index} 深度={(pole.co.y-c.y)*1000:.1f}mm | "
          f"极点连面={len(pole.link_faces)} (三角={len(tri)} 四边={len(quad)}) 期望M={expect_M} | "
          f"末环顶点数={len(last_ring)} 期望={expect_M}")
    ok = len(tri) == expect_M and len(quad) == 0 and len(last_ring) == expect_M
    print(f"  → {'✅ 碗底极点扇完好' if ok else '⚠️ 碗底结构与期望不符'}")
bm.free()
