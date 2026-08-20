"""诊断L眼碗底三角扇55/84缺失: 按径向分带统计环顶点数+面数, 定位坍缩位置.
假设: remove_doubles(0.1mm)或sliver溶解吃掉了碗底(末环相邻顶点间距≈0.09mm<0.1mm)."""
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

for side, M in (("L", 84), ("R", 74)):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < 0.030]
    print(f"=== {side}眼 (期望M={M}) ===")
    # 径向分带(0.25mm带宽), 统计每带顶点数
    bands = {}
    for v in lv:
        r = Vector((v.co.x - c.x, 0, v.co.z - c.z)).length * 1000  # mm
        b = int(r // 0.25)
        bands.setdefault(b, []).append(v)
    for b in sorted(bands.keys())[:14]:  # 前3.5mm
        vs = bands[b]
        # 该带顶点的平均link边数
        avg_val = sum(len(v.link_edges) for v in vs) / len(vs)
        print(f"  径向{b*0.25:.2f}-{(b+1)*0.25:.2f}mm: {len(vs)}顶点 均价数={avg_val:.1f}")
    # 极点详情
    cand = [v for v in lv if Vector((v.co.x-c.x,0,v.co.z-c.z)).length < 0.0005]
    if cand:
        pole = max(cand, key=lambda v: v.co.y)
        print(f"  极点: {len(pole.link_faces)}面 {len(pole.link_edges)}边")
        # 极点相邻环(与极点共享边的顶点)的径向距离分布
        nbrs = [e.other_vert(pole) for e in pole.link_edges]
        rs = sorted(Vector((v.co.x-c.x,0,v.co.z-c.z)).length*1000 for v in nbrs)
        print(f"  极点邻环顶点数={len(nbrs)} 径向范围={rs[0]:.3f}~{rs[-1]:.3f}mm")
        # 邻环上相邻顶点间距
        import math
        gaps = []
        ang = sorted((math.atan2(v.co.z-c.z, v.co.x-c.x), v) for v in nbrs)
        for i in range(len(ang)):
            a, va = ang[i]; _, vb = ang[(i+1) % len(ang)]
            gaps.append((va.co - vb.co).length * 1000)
        print(f"  邻环相邻间距: min={min(gaps):.4f}mm max={max(gaps):.4f}mm")
bm.free()
