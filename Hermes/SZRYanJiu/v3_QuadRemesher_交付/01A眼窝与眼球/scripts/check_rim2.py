"""精确测 ring0 (开孔边界环) 半径, 复用 make_eye_cup 的开放边环提取逻辑"""
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
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()

for side, center in [("L", cL), ("R", cR)]:
    def in_zone(co):
        dxz = (co - center).xz.length
        return 0.005 < dxz < 0.025
    open_edges = [e for e in bm.edges if len(e.link_faces)==1 and in_zone(e.verts[0].co)]
    adj = defaultdict(list)
    for e in open_edges:
        adj[e.verts[0].index].append(e.verts[1].index)
        adj[e.verts[1].index].append(e.verts[0].index)
    # 拓扑行走提取环
    visited_v = set(); rings = []
    for start in list(adj.keys()):
        if start in visited_v or len(adj[start]) != 2: continue
        ring = [start]; visited_v.add(start)
        prev, cur = -1, start; closed = False
        for _ in range(10000):
            nxt = None
            for n in adj[cur]:
                if n == prev: continue
                if n == start: closed = True; break
                if n not in visited_v: nxt = n; break
            if closed or nxt is None: break
            ring.append(nxt); visited_v.add(nxt)
            prev, cur = cur, nxt
        if closed and len(ring) >= 3: rings.append(ring)
    ring_idx = max(rings, key=len)
    ring0 = [bm.verts[i] for i in ring_idx]
    M = len(ring0)
    # 半径分布
    radii = [((v.co-center).xz.length)*1000 for v in ring0]
    angs = [math.degrees(math.atan2(v.co.z-center.z, v.co.x-center.x)) for v in ring0]
    jumps = [abs(radii[(i+1)%M]-radii[i]) for i in range(M)]
    print(f"{side}: ring0 M={M}, 半径[{min(radii):.1f},{max(radii):.1f}]mm avg={sum(radii)/M:.1f}mm, 跳变avg={sum(jumps)/M:.2f}max={max(jumps):.2f}mm")
    # 按象限
    quad = {"外眼角(x<0侧最远)": [], "内眼角(x>0侧最远)": [], "上睑(z大)": [], "下睑(z小)": []}
    for a, r in zip(angs, radii):
        pass
    # 直接分角度桶(仅ring0, 无皮肤污染)
    print(f"  分角度半径(每30°):")
    for deg in range(-180, 180, 30):
        lo, hi = deg-15, deg+15
        rs = []
        for a, r in zip(angs, radii):
            a = a if a <= 180 else a-360
            if lo <= a < hi: rs.append(r)
        if rs:
            print(f"    {deg:>4}°: {sum(rs)/len(rs):.1f}mm (n={len(rs)})")
bm.free()