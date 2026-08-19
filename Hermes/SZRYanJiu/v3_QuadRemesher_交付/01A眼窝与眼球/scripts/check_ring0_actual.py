"""精确测量 ring0 (开孔边界环) 的实际位置
rim 半径 avg=8.3mm 是错的, 实际 ring0 在 ~15mm
"""
import bpy, os, sys, json, math
from mathutils import Vector
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.edges.ensure_lookup_table()

for side, center in [("L", cL), ("R", cR)]:
    # 找眼窝区开放边(碗面入口)
    open_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
            if dxz < 0.025:  # 25mm内
                open_edges.append(e)
    print(f"\n{side}: 开放边总数={len(open_edges)}")
    if open_edges:
        # 找最大环
        adj = defaultdict(list)
        for e in open_edges:
            adj[e.verts[0].index].append(e.verts[1].index)
            adj[e.verts[1].index].append(e.verts[0].index)
        rings = []; visited = set()
        for start in list(adj.keys()):
            if start in visited or len(adj[start]) != 2: continue
            ring = [start]; visited.add(start)
            prev, cur = -1, start; closed = False
            for _ in range(10000):
                nxt = None
                for n in adj[cur]:
                    if n == prev: continue
                    if n == start: closed = True; break
                    if n not in visited: nxt = n; break
                if closed or nxt is None: break
                ring.append(nxt); visited.add(nxt); prev, cur = cur, nxt
            if closed and len(ring) >= 3: rings.append(ring)
        print(f"  开放边环数={len(rings)}")
        for i, ring in enumerate(sorted(rings, key=len, reverse=True)[:3]):
            pts = [bm.verts[j].co for j in ring]
            radii = [((p-center).xz.length)*1000 for p in pts]
            print(f"  环{i}: {len(ring)}顶点, 半径{min(radii):.1f}~{max(radii):.1f}mm avg={sum(radii)/len(radii):.1f}mm")
            # 按象限
            for q, name in [((0,90),"外上"), ((90,180),"内上"), ((180,270),"内下"), ((270,360),"外下")]:
                qrs = [r for p, r in zip(pts, radii) if q[0] <= math.degrees(math.atan2(p.z-center.z, p.x-center.x)) % 360 < q[1]]
                if qrs:
                    print(f"    {name}: {min(qrs):.1f}~{max(qrs):.1f}mm")
bm.free()
print("\n诊断完成")
