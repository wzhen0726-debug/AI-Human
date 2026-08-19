"""检查输入模型的开口边界 vs 3DDFA轮廓"""
import bpy, os, sys, json, math
from mathutils import Vector
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.edges.ensure_lookup_table()

for side, center in [("L", cL), ("R", cR)]:
    # 找眼窝区开放边
    open_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
            if dxz < 0.025:
                open_edges.append(e)
    print(f"\n{side}: 开放边={len(open_edges)}")
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
        ring_idx = max(rings, key=len)
        ring0 = [bm.verts[i].co.copy() for i in ring_idx]
        radii = [((v-center).xz.length)*1000 for v in ring0]
        print(f"  输入模型开口环: {len(ring0)}顶点, 半径{min(radii):.1f}~{max(radii):.1f}mm avg={sum(radii)/len(radii):.1f}mm")
        
        # 对比3DDFA轮廓
        with open(EYELID_CONTOUR_JSON, encoding="utf-8") as f:
            dd = json.load(f)
        rim_3ddfa = [Vector((r[0], r[1], r[2])) for r in dd[side]["rim_3d"] if r is not None]
        dists = [min((v - p).length for p in rim_3ddfa)*1000 for v in ring0]
        print(f"  开口环→3DDFA距离: min={min(dists):.1f} max={max(dists):.1f} avg={sum(dists)/len(dists):.1f}mm")
bm.free()
print("\n诊断完成")
