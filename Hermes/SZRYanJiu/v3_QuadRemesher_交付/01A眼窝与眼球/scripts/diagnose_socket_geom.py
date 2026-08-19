"""diagnose_socket_geom: 眼窝区几何定量诊断
1. 平滑/平直着色统计(碗面flat shading会显锯齿)
2. BVH射线: 从前往后打光线,数眼窝区穿越次数(>1=双层几何/眼球残留)
3. 眼窝区内部面片统计(y深度直方图)
"""
import bpy, os, sys, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.faces.ensure_lookup_table()

print("=== 1. 着色统计(眼窝区 dxz<22mm) ===")
for side, center in [("L", cL), ("R", cR)]:
    flat = smooth = 0
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = ((fc.x-center.x)**2 + (fc.z-center.z)**2) ** 0.5
        if dxz < 0.022:
            if f.smooth:
                smooth += 1
            else:
                flat += 1
    print(f"  {side}: smooth={smooth} flat={flat}")

print("\n=== 2. BVH 射线穿越计数(检测双层几何) ===")
mesh = obj.data
mesh.calc_loop_triangles()
bvh = BVHTree.FromPolygons(
    [v.co.copy() for v in bm.verts],
    [tuple(v.index for v in f.verts) for f in bm.faces], all_triangles=False, epsilon=0.0)

for side, center in [("L", cL), ("R", cR)]:
    multi = 0; total = 0; extra_hits = []
    # 网格射线: xz ±16mm 步长2mm
    n = 16
    for i in range(-n, n+1, 2):
        for k in range(-n, n+1, 2):
            x = center.x + i*0.001; z = center.z + k*0.001
            if (i*i + k*k) > n*n: continue
            origin = Vector((x, center.y - 0.05, z))
            dirv = Vector((0, 1, 0))
            # 最多数5次穿越, 窗口 y < center.y+0.030 (30mm深, 避开后脑壳)
            hits = []
            o = origin.copy()
            for _ in range(5):
                loc, norm, idx, dist = bvh.ray_cast(o, dirv)
                if loc is None: break
                if loc.y > center.y + 0.030: break
                hits.append(round((loc.y - center.y)*1000, 1))  # 深度mm
                o = loc + dirv * 0.0005
            total += 1
            if len(hits) > 1:
                multi += 1
                extra_hits.append(hits)
    print(f"  {side}: 射线总数={total}, 多次穿越射线={multi} ({multi/max(total,1)*100:.0f}%)")
    for h in extra_hits[:12]:
        print(f"    穿越深度序列(mm): {h}")

print("\n=== 3. 眼窝区内部几何 y 深度直方图(面片质心) ===")
for side, center in [("L", cL), ("R", cR)]:
    hist = {}
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = ((fc.x-center.x)**2 + (fc.z-center.z)**2) ** 0.5
        if dxz < 0.020:
            depth = (fc.y - center.y) * 1000
            bucket = int(depth // 5) * 5
            hist[bucket] = hist.get(bucket, 0) + 1
    print(f"  {side}: 深度桶(mm)->面数: {dict(sorted(hist.items()))}")

print("\n=== 4. 非流形边统计(眼窝区) ===")
for side, center in [("L", cL), ("R", cR)]:
    nm = 0
    for e in bm.edges:
        if len(e.link_faces) not in (1, 2):
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = ((ec.x-center.x)**2 + (ec.z-center.z)**2) ** 0.5
            if dxz < 0.022:
                nm += 1
    print(f"  {side}: 非流形边={nm}")

bm.free()
print("\n诊断完成")
