"""diagnose_t3_rim.py - t3定量诊断: 眼裂形状偏宽偏圆 + 内外眼角碎片
测量(全部定量, 不靠vision):
A. 输出blend里每只眼: 碎片(断连面片)检测 + 接缝环形状(宽/高/宽高比) vs 3DDFA轮廓
B. 常数UV面分布(哪些原始皮肤面被UV覆盖)
C. 输入blend里贴图画的眼睛实际范围(暗色像素的XZ包围盒) vs 开孔轮廓尺寸
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def point_in_polygon(x, z, poly):
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, zi = poly[i]; xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside

with open(DDFA_JSON, encoding="utf-8") as f:
    dd = json.load(f)
centers = {"L": Vector(dd["L"]["center_3d"]), "R": Vector(dd["R"]["center_3d"])}

def contour_poly(side, cx, cz):
    d = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
    return [(r[0]-cx, r[2]-cz) for r in d[side]["rim_3d"] if r is not None]

# ============ A. 输出blend: 碎片 + 接缝环 ============
print("=" * 70)
print("A. OUTPUT blend 01_1: islands + seam rings")
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data
uv_layer = me.uv_layers.active

for side in ("L", "R"):
    c = centers[side]
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    # --- A1. 碎片检测: 眼区30mm内面片的连通分量 ---
    zone = [f for f in bm.faces
            if math.hypot(f.calc_center_median().x-c.x, f.calc_center_median().z-c.z) < 0.030
            and f.calc_center_median().y < c.y + 0.02]
    zf = set(f.index for f in zone)
    adj = defaultdict(list)
    for f in zone:
        for e in f.edges:
            for lf in e.link_faces:
                if lf.index != f.index and lf.index in zf:
                    adj[f.index].append(lf.index)
    comp = {}; cid = 0
    for f in zone:
        if f.index in comp: continue
        cid += 1; stack = [f.index]; comp[f.index] = cid
        while stack:
            fi = stack.pop()
            for nb in adj[fi]:
                if nb not in comp:
                    comp[nb] = cid; stack.append(nb)
    sizes = defaultdict(list)
    for fi, ci in comp.items(): sizes[ci].append(fi)
    sizes = sorted(sizes.values(), key=len, reverse=True)
    print(f"\n--- {side} eye connectivity: {len(sizes)} components in zone ---")
    print(f"  main: {len(sizes[0])} faces")
    for k, comp_faces in enumerate(sizes[1:6], 1):
        fs = [bm.faces[i] for i in comp_faces]
        ctr = sum((f.calc_center_median() for f in fs), Vector()) / len(fs)
        dxz = math.hypot(ctr.x-c.x, ctr.z-c.z) * 1000
        ymin = min(f.calc_center_median().y for f in fs)*1000
        ymax = max(f.calc_center_median().y for f in fs)*1000
        print(f"  ISLAND{k}: {len(comp_faces)} faces, center dxz={dxz:.1f}mm, "
              f"dx={(ctr.x-c.x)*1000:+.1f} dz={(ctr.z-c.z)*1000:+.1f}mm, "
              f"y=[{ymin-c.y*1000:.1f},{ymax-c.y*1000:.1f}]mm rel")
    # --- A2. 接缝环: 常数UV面 vs 变化UV面 的边界边 ---
    def is_const_uv(f):
        uvs = [loop[uv_layer].uv for loop in f.loops]
        u0 = uvs[0]
        return all((u - u0).length < 0.002 for u in uvs[1:])
    seam_verts = set()
    for f in zone:
        cu = is_const_uv(f)
        for e in f.edges:
            for lf in e.link_faces:
                if lf.index in zf and is_const_uv(lf) != cu:
                    seam_verts.add(e.verts[0]); seam_verts.add(e.verts[1])
                    break
    if len(seam_verts) >= 3:
        ring = sorted(seam_verts, key=lambda v: math.atan2(v.co.z-c.z, v.co.x-c.x))
        xs = [v.co.x for v in ring]; zs = [v.co.z for v in ring]
        w = (max(xs)-min(xs))*1000; h = (max(zs)-min(zs))*1000
        radii = [math.hypot(v.co.x-c.x, v.co.z-c.z)*1000 for v in ring]
        print(f"  SEAM ring: {len(ring)} verts, width={w:.1f}mm height={h:.1f}mm aspect={w/max(h,0.01):.2f}, "
              f"r=[{min(radii):.1f},{max(radii):.1f}] avg={sum(radii)/len(radii):.1f}mm")
    else:
        print(f"  SEAM ring: only {len(seam_verts)} verts (no clear seam)")
    # --- A3. 3DDFA轮廓参考 ---
    poly = contour_poly(side, c.x, c.z)
    px = [p[0] for p in poly]; pz = [p[1] for p in poly]
    cw = (max(px)-min(px))*1000; ch = (max(pz)-min(pz))*1000
    cr = [math.hypot(x, z)*1000 for x, z in poly]
    print(f"  3DDFA contour: width={cw:.1f}mm height={ch:.1f}mm aspect={cw/max(ch,0.01):.2f}, "
          f"r=[{min(cr):.1f},{max(cr):.1f}] avg={sum(cr)/len(cr):.1f}mm")
    # --- A4. 开放边/非流形边 ---
    open_e = [e for e in bm.edges if len(e.link_faces) == 1
              and math.hypot((e.verts[0].co.x+e.verts[1].co.x)/2-c.x,
                             (e.verts[0].co.z+e.verts[1].co.z)/2-c.z) < 0.025]
    nm_e = [e for e in bm.edges if len(e.link_faces) > 2
            and math.hypot((e.verts[0].co.x+e.verts[1].co.x)/2-c.x,
                           (e.verts[0].co.z+e.verts[1].co.z)/2-c.z) < 0.025]
    print(f"  open edges={len(open_e)}, non-manifold edges={len(nm_e)} (zone<25mm)")
    # --- A5. 常数UV面在15-21mm原始皮肤区的数量(判断是否误覆盖) ---
    # 原始皮肤面 ≈ 法线朝-Y且不在碗内; 简化: 统计15-21mm带内常数UV面
    band_const = 0; band_total = 0
    for f in zone:
        fc = f.calc_center_median()
        dxz = math.hypot(fc.x-c.x, fc.z-c.z)
        if 0.015 < dxz < 0.021 and abs(fc.y - c.y) < 0.02:
            band_total += 1
            if is_const_uv(f): band_const += 1
    print(f"  15-21mm band: {band_const}/{band_total} faces have CONSTANT uv (overwritten)")
    bm.free()

# ============ B. 输入blend: 贴图眼睛实际范围 ============
print("=" * 70)
print("B. INPUT blend: painted-eye extent from texture dark pixels")
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data
uv_layer = me.uv_layers.active
tex_img = None
for m in obj.data.materials:
    if m and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
px = np.array(tex_img.pixels[:], dtype=np.float32).reshape(tex_img.size[1], tex_img.size[0], 4)
TW, TH = tex_img.size
print(f"texture: {tex_img.name} {TW}x{TH}")

for side in ("L", "R"):
    c = centers[side]
    poly = contour_poly(side, c.x, c.z)
    # 轮廓外扩3mm做多边形(含睫毛区)
    exp_poly = []
    cxm = sum(p[0] for p in poly)/len(poly); czm = sum(p[1] for p in poly)/len(poly)
    for x, z in poly:
        dx, dz = x-cxm, z-czm
        d = math.hypot(dx, dz)
        exp_poly.append((x + dx/d*0.003, z + dz/d*0.003) if d > 1e-9 else (x, z))
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    dark_pts = []; all_pts = []
    for f in bm.faces:
        fc = f.calc_center_median()
        if fc.y >= c.y + 0.020: continue
        if not point_in_polygon(fc.x, fc.z, exp_poly): continue
        for loop in f.loops:
            uv = loop[uv_layer].uv
            if not (0.01 < uv.x < 0.99 and 0.01 < uv.y < 0.99): continue
            co = loop.vert.co
            dxx, dzz = (co.x-c.x)*1000, (co.z-c.z)*1000
            all_pts.append((dxx, dzz))
            xi = min(int(uv.x*TW), TW-1); yi = min(int(uv.y*TH), TH-1)
            lum = float(px[yi, xi, :3].mean())
            if lum < 0.30:   # 暗色=睫毛/眼线/虹膜边缘
                dark_pts.append((dxx, dzz, lum))
    bm.free()
    if dark_pts:
        da = np.array(dark_pts)
        aa = np.array(all_pts)
        print(f"\n--- {side} painted eye (dark pixels<0.30) ---")
        print(f"  dark samples: {len(dark_pts)}/{len(all_pts)} ({100*len(dark_pts)/max(len(all_pts),1):.1f}%)")
        print(f"  dark XZ bbox: x=[{da[:,0].min():.1f},{da[:,0].max():.1f}]mm ({da[:,0].ptp():.1f}mm wide), "
              f"z=[{da[:,1].min():.1f},{da[:,1].max():.1f}]mm ({da[:,1].ptp():.1f}mm tall)")
        print(f"  all captured XZ bbox: x=[{aa[:,0].min():.1f},{aa[:,0].max():.1f}] ({aa[:,0].ptp():.1f}mm), "
              f"z=[{aa[:,1].min():.1f},{aa[:,1].max():.1f}] ({aa[:,1].ptp():.1f}mm)")
        # 虹膜/瞳孔核心(最暗10%)的中心与半径
        core = da[da[:,2] < np.percentile(da[:,2], 10)]
        ccx, ccz = core[:,0].mean(), core[:,1].mean()
        rr = np.sqrt((core[:,0]-ccx)**2 + (core[:,1]-ccz)**2).max()
        print(f"  darkest-10% core: center=({ccx:+.1f},{ccz:+.1f})mm rel eye-center, radius={rr:.1f}mm")
    else:
        print(f"\n--- {side}: NO dark samples captured ---")
print("=" * 70)
print("DIAG DONE")
