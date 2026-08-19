"""diagnose_seam_fit: 交缝精准度定量
输入模型是睁眼状态: 眼睑皮肤有开口, 眼球从中露出.
眼裂 = 眼睑开口的边界环(开放边 或 眼睑-眼球锐利折边).
1. 在输入模型眼周找开放边/锐折边 → 眼裂轮廓
2. 与我们管线的 rim 轮廓(开孔边界环)对比: 逐角度径向偏差
"""
import bpy, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def get_rim_from_output():
    """从v40输出读rim轮廓(碗面与倒角带交界=最浅一圈, y≈center.y)"""
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    rims = {}
    for side, center in [("L", cL), ("R", cR)]:
        # rim顶点: dxz 13-20mm, y在center.y±1.5mm
        pts = []
        for v in bm.verts:
            dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
            if 0.013 < dxz < 0.020 and abs(v.co.y - center.y) < 0.0015:
                ang = math.atan2(v.co.z - center.z, v.co.x - center.x)
                pts.append((ang, dxz*1000))
        # 每10度取平均半径
        rim_r = {}
        for deg in range(0, 360, 10):
            a0, a1 = math.radians(deg-18), math.radians(deg+18)
            rs = [r for a, r in pts if a0 <= a < a1]
            if rs:
                rim_r[deg] = sum(rs)/len(rs)
        rims[side] = rim_r
    bm.free()
    return rims, cL, cR

def get_slit_from_input():
    """输入模型眼裂: 眼周开放边 + 锐利折边(二面角>50度且两侧法线差异大)"""
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    slits = {}
    for side, center in [("L", cL), ("R", cR)]:
        pts = []
        for e in bm.edges:
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
            if not (0.008 < dxz < 0.020): continue
            if abs(ec.y - center.y) > 0.008: continue
            is_slit = False
            if len(e.link_faces) == 1:
                is_slit = True  # 开放边=眼睑开孔边界
            elif len(e.link_faces) == 2:
                f0, f1 = e.link_faces
                dot = f0.normal.dot(f1.normal)
                # 锐折边: 眼睑(朝-Y)与眼球(朝外)交界
                if dot < 0.5 and f0.normal.y * f1.normal.y < 0.3:
                    is_slit = True
            if is_slit:
                ang = math.atan2(ec.z - center.z, ec.x - center.x)
                pts.append((ang, dxz*1000))
        slit_r = {}
        for deg in range(0, 360, 10):
            a0, a1 = math.radians(deg-18), math.radians(deg+18)
            rs = [r for a, r in pts if a0 <= a < a1]
            if rs:
                slit_r[deg] = sum(rs)/len(rs)
        slits[side] = (slit_r, len(pts))
    bm.free()
    return slits

rims, cL, cR = get_rim_from_output()
slits = get_slit_from_input()

print("="*70)
print("交缝精准度: 输出rim轮廓 vs 输入模型眼裂轮廓 (半径mm, 逐10度)")
print("="*70)
for side in ["L", "R"]:
    rim_r = rims[side]
    slit_r, n_pts = slits[side]
    print(f"\n{side} 眼 (眼裂候选边={n_pts}):")
    if not slit_r:
        print("  !! 输入模型未找到眼裂边界(眼睑可能与眼球连续无折边)")
        continue
    print(f"  {'角度':>6} {'rim半径':>8} {'眼裂半径':>8} {'偏差':>8}")
    devs = []
    for deg in sorted(set(rim_r) & set(slit_r)):
        dev = rim_r[deg] - slit_r[deg]
        devs.append(dev)
        print(f"  {deg:>5}° {rim_r[deg]:>8.1f} {slit_r[deg]:>8.1f} {dev:>+8.1f}")
    if devs:
        print(f"  偏差: avg={sum(devs)/len(devs):+.2f}mm "
              f"abs_avg={sum(abs(d) for d in devs)/len(devs):.2f}mm "
              f"max={max(abs(d) for d in devs):.2f}mm 覆盖{len(devs)}/36角度")
print("\n诊断完成")
