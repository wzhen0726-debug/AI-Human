# 眼区网格体检(QR 前置): 开放边归属 / n-gon / 细长面分档 / 重复顶点 / 非流形 / rim 环闭合
#
# 用法:  EYE_OUT_BLEND=<产物.blend> EYE_CONTOUR_JSON=<手描轮廓.json> blender -b --factory-startup --python mesh_health_check.py
# 合格线: 眼周 8mm 内 n-gon=0 / 长边>2mm=0 / 退化面≈0 / 重复顶点=0 / 开放边只存在于 rim 环(1 度 0, 分叉 0)。
# 归属判定: 对 ①输入文件 ②改动前备份 ③当前产物 各跑一遍 —— 三态都有的缺陷是输入自带的, 不要修。
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

F = os.environ.get("EYE_OUT_BLEND")
J = os.environ.get("EYE_CONTOUR_JSON")
assert F and J, "需要环境变量 EYE_OUT_BLEND 与 EYE_CONTOUR_JSON"
print("检查:", os.path.basename(F))
bpy.ops.wm.open_mainfile(filepath=F)
Jd = json.load(open(J, encoding="utf-8"))
head = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
bm = bmesh.new(); bm.from_mesh(head.data)
bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.normal_update()

# 左右眼(屏幕左右)中心 + 手描轮廓 XZ
EYE = {}
for side in ("L", "R"):
    c = Jd[side]["center"]
    EYE[side] = (Vector((float(c[0]), float(c[1]), float(c[2]))),
                 np.array([[float(p[0]), float(p[2])] for p in Jd[side]["rim_3d"]]))

def d_contour(x, z):
    return min(float(np.sqrt((P[:, 0] - x) ** 2 + (P[:, 1] - z) ** 2).min()) for _cv, P in EYE.values())

# ① 开放边: 眼周(<6mm) vs 远离眼(远离眼的多半是输入自带, 要认出来别当自己的 bug)
oe = [e for e in bm.edges if len(e.link_faces) == 1]
near = 0
far = []
for e in oe:
    v = e.verts[0].co
    d = d_contour(v.x, v.z)
    if d < 0.006:
        near += 1
    else:
        far.append((v.copy(), d))
print(f"开放边 {len(oe)}: 眼周(<6mm) {near}, 远离眼 {len(far)}")
for v, d in far[:6]:
    print(f"   远离眼的开放边 @({v.x*1000:.1f},{v.y*1000:.1f},{v.z*1000:.1f}) 距轮廓{d*1000:.1f}mm")

# ② n-gon / ③ 细长面(按长边分档) / ④ 非流形
cls = {"<1mm": 0, "1-2mm": 0, ">2mm": 0}
mx = 0.0
ng = 0
ngd = []
for f in bm.faces:
    c = f.calc_center_median()
    if min((c - cv).xz.length for cv, _P in EYE.values()) > 0.030:
        continue
    if c.y > min(cv.y for cv, _P in EYE.values()) + 0.02:   # 只排后脑, 别把眼周皮肤排掉
        continue
    if d_contour(c.x, c.z) > 0.008:
        continue
    if len(f.verts) > 4:
        ng += 1
        ngd.append((d_contour(c.x, c.z), c.copy()))
    ls = sorted(e.calc_length() for e in f.edges)
    if ls[0] > 1e-9 and ls[-1] / ls[0] > 6:
        L = ls[-1]
        mx = max(mx, L)
        cls["<1mm" if L < 0.001 else ("1-2mm" if L < 0.002 else ">2mm")] += 1
nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
print(f"眼周8mm: n-gon(>4边) {ng} | 细长面(长宽比>6) {cls} 最长{mx*1000:.2f}mm | 全局非流形边 {nm}")
for d, c in ngd[:4]:
    print(f"   n-gon @({c.x*1000:.1f},{c.y*1000:.1f},{c.z*1000:.1f}) 距轮廓{d*1000:.2f}mm")

# ⑤ 重复顶点(眼周, 阈值 0.02mm)
for side, (cv, P) in EYE.items():
    vs = [v for v in bm.verts if np.sqrt((P[:, 0] - v.co.x) ** 2 + (P[:, 1] - v.co.z) ** 2).min() < 0.004]
    if not vs:
        continue
    kd = KDTree(len(vs))
    for i, v in enumerate(vs):
        kd.insert(v.co, i)
    kd.balance()
    dup = 0
    for i, v in enumerate(vs):
        for _co, idx, _dist in kd.find_range(v.co, 0.00002):
            if idx != i:
                dup += 1
    print(f"{side}: 眼周4mm内顶点 {len(vs)}, 距离<0.02mm 的重复对 {dup // 2}")

# ⑥ rim 环闭合(1 度=断开, >=3 度=分叉; 两者都为 0 才是单一闭环)
for side, (cv, P) in EYE.items():
    oe2 = [e for e in bm.edges if len(e.link_faces) == 1
           and (e.verts[0].co - cv).xz.length < 0.05 and e.verts[0].co.y < cv.y + 0.02]
    deg = {}
    for e in oe2:
        a, b = e.verts
        for x, y in ((a, b), (b, a)):
            deg.setdefault((x.co.x, x.co.y, x.co.z), []).append((y.co.x, y.co.y, y.co.z))
    n1 = sum(1 for k in deg if len(deg[k]) == 1)
    n3 = sum(1 for k in deg if len(deg[k]) >= 3)
    print(f"{side}: 边界边{len(oe2)} 端点{len(deg)} | 1度(断开){n1} | >=3度(分叉){n3} | "
          f"{'单一闭环 OK' if n1 == 0 and n3 == 0 else '有开口/分叉 NG'}")
bm.free()
print("体检完成")
