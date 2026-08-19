"""验证: ring0 松弛前 vs 松弛后的形状变化"""
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
    # 找眼窝区开放边环(碗面入口)
    open_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
            if dxz < 0.020:
                open_edges.append(e)
    if not open_edges:
        print(f"{side}: 无开放边")
        continue
    
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
    ring0 = [bm.verts[i] for i in ring_idx]
    
    print(f"\n{side}: ring0 M={len(ring0)}")
    # 当前位置(松弛后)
    radii_after = [((v.co-center).xz.length)*1000 for v in ring0]
    print(f"  松弛后半径: {min(radii_after):.1f}~{max(radii_after):.1f}mm avg={sum(radii_after)/len(radii_after):.1f}mm")
    
    # 模拟松弛前(找最近邻的原始轮廓点)
    # 从3DDFA轮廓找对应点
    with open(EYELID_CONTOUR_JSON, encoding="utf-8") as f:
        dd = json.load(f)
    rim_3ddfa = [r for r in dd[side]["rim_3d"] if r is not None]
    c = dd[side]["center"]
    contour_pts = [Vector((r[0], r[1], r[2])) for r in rim_3ddfa]
    
    # 对ring0每个顶点, 找最近的3DDFA轮廓点
    dists = []
    for v in ring0:
        best = min((v.co - p).length for p in contour_pts)
        dists.append(best * 1000)
    print(f"  ring0→3DDFA轮廓距离: min={min(dists):.1f} max={max(dists):.1f} avg={sum(dists)/len(dists):.1f}mm")
    
    # 检查是否有顶点被拉远
    far = sum(1 for d in dists if d > 2.0)
    print(f"  距离>2mm的顶点: {far}/{len(ring0)} ({far/len(ring0)*100:.0f}%)")

bm.free()
print("\n诊断完成")
