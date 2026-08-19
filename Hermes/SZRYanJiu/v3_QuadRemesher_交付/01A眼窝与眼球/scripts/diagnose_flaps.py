"""diagnose_flaps: 定位"锯齿薄片"的精确空间分布
1. 统计眼窝区(dxz<25mm)所有面片, 按 (dxz桶, y深度桶) 二维分布
2. 找出非碗面的"多余"面片(不在皮肤表面层/不在碗面)
3. 对比: 输入模型同区域的面片分布
"""
import bpy, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def analyze(filepath, label):
    bpy.ops.wm.open_mainfile(filepath=filepath)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    print(f"\n{'='*60}\n{label}: {filepath.split(chr(92))[-1]}\n{'='*60}")
    for side, center in [("L", cL), ("R", cR)]:
        # 面片分类: 皮肤表面(y<center.y+2mm) vs 碗内(y>center.y+2mm)
        skin_faces = []; inner_faces = []
        for f in bm.faces:
            fc = f.calc_center_median()
            dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
            if dxz >= 0.025: continue
            depth_mm = (fc.y - center.y) * 1000
            if depth_mm < 2:
                skin_faces.append((round(dxz*1000), round(depth_mm)))
            else:
                inner_faces.append((round(dxz*1000), round(depth_mm)))
        print(f"  {side}: 皮肤表面面片={len(skin_faces)}, 头内面片={len(inner_faces)}")
        # 皮肤表面面片的 dxz 分布(看rim附近有没有多余碎片)
        dxz_hist = {}
        for dxz_mm, _ in skin_faces:
            b = int(dxz_mm // 3) * 3
            dxz_hist[b] = dxz_hist.get(b, 0) + 1
        print(f"    皮肤面dxz分布(mm桶): {dict(sorted(dxz_hist.items()))}")
        # rim 区域(dxz 13-18mm)的皮肤面片深度分布
        rim_depths = [d_mm for dxz_mm, d_mm in skin_faces if 13 <= dxz_mm <= 18]
        if rim_depths:
            print(f"    rim区(dxz13-18mm)面片深度: min={min(rim_depths)} max={max(rim_depths)} n={len(rim_depths)}")
    bm.free()

analyze(IN_BLEND, "输入模型(未处理)")
analyze(OUT_BLEND, "01A管线输出(v40)")
print("\n诊断完成")
