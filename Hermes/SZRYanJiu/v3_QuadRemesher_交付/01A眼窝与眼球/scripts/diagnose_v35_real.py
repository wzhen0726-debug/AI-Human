"""诊断v35产物: 倒角带几何/法线分桶/UV分布/smooth状态"""
import bpy, bmesh, json, os, sys
from mathutils import Vector
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"])
cR = Vector(d["R"]["center_3d"])

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

for side, center in [("L", cL), ("R", cR)]:
    print(f"\n{'='*60}")
    print(f"  {side} (center.y={center.y:.4f})")
    print(f"{'='*60}")
    
    # 1. 倒角带几何诊断
    # 找 ring0 和 ring1: ring0 是皮肤与碗交界处，特征是开放边或 y 分层
    zone_faces = [f for f in bm.faces
                  if (f.calc_center_median() - center).xz.length < 0.018
                  and -0.12 < f.calc_center_median().y < -0.08]
    
    # 按 xz 距离分桶
    buckets = {"0-8mm": [], "8-12mm": [], "12-16mm": [], "16-20mm": []}
    for f in zone_faces:
        d = (f.calc_center_median() - center).xz.length * 1000
        if d < 8: buckets["0-8mm"].append(f)
        elif d < 12: buckets["8-12mm"].append(f)
        elif d < 16: buckets["12-16mm"].append(f)
        else: buckets["16-20mm"].append(f)
    
    print(f"\n  --- 1. 面法线朝向 (按xz距离分桶) ---")
    for bname, faces in buckets.items():
        if not faces: continue
        toward = sum(1 for f in faces if f.normal.dot(center - f.calc_center_median()) > 0)
        pct = toward / len(faces) * 100
        bar = "*" * int(pct/5) + "-" * (20 - int(pct/5))
        print(f"  {bname:8s}: {toward:4d}/{len(faces):4d} ({pct:5.1f}%) [{bar}]")
    
    # 2. 倒角带 vs 碗面 y 分层
    print(f"\n  --- 2. y 分层与面类型 ---")
    y_bins = defaultdict(lambda: {"face": 0, "quad": 0, "tri": 0, "smooth": 0})
    for f in zone_faces:
        fc = f.calc_center_median()
        y_key = round(fc.y * 1000)  # mm
        y_bins[y_key]["face"] += 1
        if len(f.verts) == 4: y_bins[y_key]["quad"] += 1
        elif len(f.verts) == 3: y_bins[y_key]["tri"] += 1
        if f.smooth: y_bins[y_key]["smooth"] += 1
    
    for yk in sorted(y_bins.keys()):
        info = y_bins[yk]
        print(f"  y={yk:4d}mm: {info['face']:4d}面 (q:{info['quad']} t:{info['tri']}) smooth={info['smooth']}")
    
    # 3. 倒角带宽度 (ring0 → ring1 xz距离)
    print(f"\n  --- 3. 倒角带诊断 ---")
    # 找 y≈center.y 的 quad 面 (倒角带在表面附近)
    rim_quads = [f for f in zone_faces
                 if len(f.verts) == 4
                 and -0.108 < f.calc_center_median().y < -0.102]
    if rim_quads:
        # 测量这些 quads 的径向跨度
        spans = []
        for f in rim_quads[:20]:
            d_max = 0; d_min = 999
            for v in f.verts:
                d = (v.co - center).xz.length
                d_max = max(d_max, d); d_min = min(d_min, d)
            spans.append((d_max - d_min) * 1000)  # mm
        print(f"  rim quads: {len(rim_quads)} 面, 径向跨度: min={min(spans):.2f}mm max={max(spans):.2f}mm avg={sum(spans)/len(spans):.2f}mm")
    else:
        print(f"  rim quads: 0 (倒角带可能不存在!)")
    
    # 4. UV 诊断
    uv_layer = bm.loops.layers.uv.active
    if uv_layer:
        print(f"\n  --- 4. UV 分布 ---")
        bowl_faces = [f for f in zone_faces
                      if f.calc_center_median().y > center.y
                      and (f.calc_center_median() - center).xz.length < 0.014]
        if bowl_faces:
            uv_xs = []; uv_ys = []
            uv_zero_count = 0
            for f in bowl_faces:
                for loop in f.loops:
                    uv = loop[uv_layer].uv
                    uv_xs.append(uv.x); uv_ys.append(uv.y)
                    if uv.x == 0 and uv.y == 0:
                        uv_zero_count += 1
            print(f"  碗面 ({len(bowl_faces)}面):")
            print(f"    UV x: [{min(uv_xs):.4f}, {max(uv_xs):.4f}] y: [{min(uv_ys):.4f}, {max(uv_ys):.4f}]")
            print(f"    UV (0,0): {uv_zero_count} corners")
        
        # 倒角带 UV
        chamfer_zone = [f for f in zone_faces
                        if len(f.verts) == 4
                        and -0.110 < f.calc_center_median().y < -0.100]
        if chamfer_zone:
            uv_cx = []; uv_cy = []; uv_cz = 0
            for f in chamfer_zone:
                for loop in f.loops:
                    uv = loop[uv_layer].uv
                    uv_cx.append(uv.x); uv_cy.append(uv.y)
                    if uv.x == 0 and uv.y == 0:
                        uv_cz += 1
            print(f"  倒角带 ({len(chamfer_zone)}面):")
            print(f"    UV x: [{min(uv_cx):.4f}, {max(uv_cx):.4f}] y: [{min(uv_cy):.4f}, {max(uv_cy):.4f}]")
            print(f"    UV (0,0): {uv_cz} corners")
    
    # 5. smooth 状态
    print(f"\n  --- 5. Smooth 状态 ---")
    smooth_count = sum(1 for f in zone_faces if f.smooth)
    flat_count = len(zone_faces) - smooth_count
    print(f"  zone内: smooth={smooth_count} flat={flat_count} ({smooth_count/len(zone_faces)*100:.1f}%)")

bm.free()
print("\nDone.")