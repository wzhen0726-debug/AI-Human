"""hermes-verify: v32 端到端验证 (从输入模型完整重跑管线, 逐项检查)

用法: blender -b --python hermes_verify_v32.py
"""
import bpy, bmesh, json, os, sys
from mathutils import Vector
from collections import defaultdict

# ── 导入管线模块 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *
from iris_detect import detect_iris_centers
from socket_ops import make_eye_socket, make_eye_cup, load_eyelid_contour

# ── 辅助函数 ──
def point_in_polygon(x, z, poly):
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, zi = poly[i]; xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside

def load_3ddfa_centers():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = Vector(d["L"]["center_3d"])
    cR = Vector(d["R"]["center_3d"])
    return cL, cR

# ── 主流程 ──
results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'} {name}: {detail}")

print("=== hermes-verify v32: 端到端 (从输入模型重跑) ===")

# 1. 加载输入模型
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"Loaded: {obj.name} ({len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces)")

# 删 custom_normal
attr = obj.data.attributes.get('custom_normal')
if attr:
    obj.data.attributes.remove(attr)
    print("Removed custom_normal at load")

# 加载眼中心
cL, cR = load_3ddfa_centers()
print(f"Eye centers: L={cL}mm, R={cR}mm")

# 管线
make_eye_socket(obj, cL, "L")
make_eye_cup(obj, cL, "L")
make_eye_socket(obj, cR, "R")
make_eye_cup(obj, cR, "R")

# unify (删除 custom_normal + 局部 recalc)
from run_eye_socket import unify_normals_global
unify_normals_global(obj, cL, cR)

# 保存
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")

# ══════════════════════════════════════════
# 验证
# ══════════════════════════════════════════
me = obj.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# A. 轮廓尺寸
for side, center in [("L", cL), ("R", cR)]:
    poly = load_eyelid_contour(side)
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    w = max(xs) - min(xs); h = max(zs) - min(zs); ztop = max(zs)
    check(f"contour_{side}_width", w > 0.030, f"{w*1000:.1f}mm")
    check(f"contour_{side}_height", h > 0.008, f"{h*1000:.1f}mm")
    check(f"contour_{side}_ztop", ztop < 1.68, f"z={ztop:.4f}")

# B. custom_normal 已删
check("custom_normal_removed", me.attributes.get('custom_normal') is None, "no custom_normal attr")

# C. 开放边
open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
check("open_edges", len(open_edges) == 0, f"{len(open_edges)}")

# D. 非流形边
non_manifold = [e for e in bm.edges if len(e.link_faces) > 2]
check("non_manifold", len(non_manifold) <= 1, f"{len(non_manifold)} (input has 1)")

# E. ngon
ngons = [f for f in bm.faces if len(f.verts) > 4]
check("ngons", len(ngons) == 0, f"{len(ngons)}")

# F. 退化面
degenerate = [f for f in bm.faces if f.calc_area() < 1e-12]
check("degenerate", len(degenerate) == 0, f"{len(degenerate)}")

# G. UV-zero quads (碗面/倒角带)
uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
uv_zero = 0
for f in bm.faces:
    if len(f.verts) <= 4:
        for loop in f.loops:
            uv = loop[uv_layer].uv
            if uv.x == 0.0 and uv.y == 0.0:
                uv_zero += 1
                break
check("UV_zero_quads", uv_zero == 0, f"{uv_zero}")

# H. 碗面法线朝开口 (覆盖全部: 碗面+倒角带, xz<0.019m, y深入头内)
for side, center in [("L", cL), ("R", cR)]:
    bowl_faces = [f for f in bm.faces
                  if center.y < f.calc_center_median().y < center.y + 0.02
                  and (f.calc_center_median() - center).xz.length < 0.019]
    if bowl_faces:
        toward_eye = sum(1 for f in bowl_faces
                         if f.normal.dot(center - f.calc_center_median()) > 0)
        ratio = toward_eye / len(bowl_faces) * 100
        check(f"bowl_normal_toward_eye_{side}", ratio > 98.0,
              f"{toward_eye}/{len(bowl_faces)} ({ratio:.1f}%)")
    else:
        check(f"bowl_normal_toward_eye_{side}", False, "no bowl faces found")

# H2. 倒角带外圈法线 (xz 14-19mm, 之前被几何兜底漏掉的部分)
for side, center in [("L", cL), ("R", cR)]:
    outer = [f for f in bm.faces
             if center.y < f.calc_center_median().y < center.y + 0.02
             and 0.014 < (f.calc_center_median() - center).xz.length < 0.019]
    if outer:
        toward = sum(1 for f in outer if f.normal.dot(center - f.calc_center_median()) > 0)
        ratio = toward / len(outer) * 100
        check(f"chamfer_outer_normal_{side}", ratio > 95.0,
              f"{toward}/{len(outer)} ({ratio:.1f}%)")
    else:
        check(f"chamfer_outer_normal_{side}", False, "no chamfer outer faces")

# I. 前脸朝内面数 (不恶化, 真实基线=输入模型删custom_normal后测)
front_inward = [f for f in bm.faces
                if f.normal.y > 0.1 and f.calc_center_median().y < 0
                and abs(f.calc_center_median().x) < 0.08
                and 1.5 < f.calc_center_median().z < 1.75]
BASELINE_FRONT_INWARD = 4319  # 输入模型删custom_normal后真实基线
check("front_inward", len(front_inward) <= BASELINE_FRONT_INWARD + 500,
      f"{len(front_inward)} (baseline={BASELINE_FRONT_INWARD})")

# J. 后脑勺误翻 (不恶化, 真实基线=输入模型删custom_normal后测)
back_wrong = [f for f in bm.faces
              if f.normal.y < -0.5 and f.calc_center_median().y > 0.05]
BASELINE_BACK_WRONG = 8920   # 输入模型自带, 管线零引入
check("back_head_wrong", len(back_wrong) == BASELINE_BACK_WRONG,
      f"{len(back_wrong)} (baseline={BASELINE_BACK_WRONG})")

# K. 眼球摆入文件存在
eyeball_path = os.path.join(os.path.dirname(OUT_BLEND), "01_2_eyeball_placed.blend")
check("eyeball_file_exists", os.path.exists(eyeball_path), eyeball_path)

# 清理
bm.free()

# ── 汇总 ──
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"\n{'='*50}")
print(f"TOTAL: {passed}/{total} PASS, {failed} FAIL")
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}: {detail}")
print(f"{'='*50}")