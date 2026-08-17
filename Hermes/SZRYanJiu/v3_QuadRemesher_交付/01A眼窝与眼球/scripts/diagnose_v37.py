"""v37 诊断: 定量检查眼窝实际几何, 定位根因.
加载 run_eye_socket.py 的产物 01_1_eye_socket.blend, 检查:
1. 开放边/非流形边 (破面)
2. 边界环 jaggedness (锯齿程度)
3. 碗面法线朝向 (分离碗面/皮肤面/倒角带面)
4. 碗面 UV 分布
"""
import bpy, bmesh, json, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

blend = OUT_BLEND
bpy.ops.wm.open_mainfile(filepath=blend)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data
print(f"=== 诊断 {blend} ===")
print(f"verts={len(me.vertices)} faces={len(me.polygons)}")

# 眼中心
def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# 1. 开放边 + 非流形边
open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
non_manifold = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"\n[1] 开放边={len(open_edges)} 非流形边={len(non_manifold)}")
for e in open_edges[:20]:
    mx = (e.verts[0].co.x + e.verts[1].co.x)/2
    mz = (e.verts[0].co.z + e.verts[1].co.z)/2
    my = (e.verts[0].co.y + e.verts[1].co.y)/2
    # 判断靠近哪只眼
    dl = (Vector((mx,my,mz)) - cL).length
    dr = (Vector((mx,my,mz)) - cR).length
    print(f"    open_edge @ ({mx*1000:.1f},{my*1000:.1f},{mz*1000:.1f})mm near={'L' if dl<dr else 'R'}")

# 2. 碗面/倒角带/皮肤面分类 + 法线朝向
for side, center in [("L", cL), ("R", cR)]:
    print(f"\n[2] {side} 面分类 (center={center})")
    # 碗面: y 在 center.y 到 center.y+0.02 之间, xz<0.019
    # 倒角带: xz 14-17.5mm (ring0半径附近), y 接近 rim
    # 皮肤: 其余
    bowl = []
    chamfer = []
    for f in bm.faces:
        fc = f.calc_center_median()
        xz = (fc - center).xz.length
        if center.y < fc.y < center.y + 0.02 and xz < 0.019:
            bowl.append(f)
        elif xz < 0.019 and fc.y < 0:
            chamfer.append(f)
    # 法线朝向: 朝眼球 = normal dot (center - fc) > 0
    if bowl:
        toward = sum(1 for f in bowl if f.normal.dot(center - f.calc_center_median()) > 0)
        print(f"  碗面: {len(bowl)} 个, 朝眼球 {toward} ({toward/len(bowl)*100:.1f}%)")
        # 分桶看法线分布
        import math
        bad = [f for f in bowl if f.normal.dot(center - f.calc_center_median()) < 0]
        if bad:
            # 坏面的位置分布
            ymin = min(f.calc_center_median().y for f in bad)
            ymax = max(f.calc_center_median().y for f in bad)
            xzmin = min((f.calc_center_median()-center).xz.length for f in bad)
            xzmax = max((f.calc_center_median()-center).xz.length for f in bad)
            print(f"  坏面 {len(bad)}: y=[{ymin:.4f},{ymax:.4f}] xz=[{xzmin*1000:.1f},{xzmax*1000:.1f}]mm")
            # 坏面是否集中在碗底极点扇?
            near_pole = sum(1 for f in bad if (f.calc_center_median()-center).xz.length < 0.003)
            print(f"    其中极点扇(xz<3mm): {near_pole}")
    else:
        print("  碗面: 无")
    if chamfer:
        toward_c = sum(1 for f in chamfer if f.normal.dot(center - f.calc_center_median()) > 0)
        print(f"  倒角带/其他面: {len(chamfer)} 个, 朝眼球 {toward_c} ({toward_c/len(chamfer)*100:.1f}%)")

# 3. 边界环 jaggedness: 找开放边, 若有则说明有破面
print(f"\n[3] 边界环分析")
# 找眼窝开口环(现在应该是封闭的, 无开放边)
# 通过找碗面与皮肤面的交界来估计 jaggedness
for side, center in [("L", cL), ("R", cR)]:
    # 找 ring0 附近顶点 (xz 半径 15-19mm 之间, y 接近 rim)
    rim_verts = [v for v in bm.verts
                 if 0.014 < (v.co - center).xz.length < 0.020
                 and abs(v.co.y - center.y) < 0.006]
    if rim_verts:
        # 按角度排序, 计算相邻顶点角度步长的均匀性
        import math
        rim_verts.sort(key=lambda v: math.atan2(v.co.z - center.z, v.co.x - center.x))
        # 计算径向距离的波动
        radii = [(v.co - center).xz.length for v in rim_verts]
        rmin, rmax = min(radii), max(radii)
        rstd = (sum((r - sum(radii)/len(radii))**2 for r in radii) / len(radii)) ** 0.5
        print(f"  {side} rim: {len(rim_verts)} verts, 径向半径 r=[{rmin*1000:.2f},{rmax*1000:.2f}]mm, std={rstd*1000:.2f}mm")

# 4. UV 分布
print(f"\n[4] UV 分布")
uv_layer = bm.loops.layers.uv.active
if uv_layer:
    for side, center in [("L", cL), ("R", cR)]:
        bowl_uvs = []
        for f in bm.faces:
            fc = f.calc_center_median()
            if center.y < fc.y < center.y + 0.02 and (fc-center).xz.length < 0.019:
                for loop in f.loops:
                    bowl_uvs.append(loop[uv_layer].uv)
        if bowl_uvs:
            us = [uv.x for uv in bowl_uvs]; vs = [uv.y for uv in bowl_uvs]
            print(f"  {side} 碗面 UV: {len(bowl_uvs)} loops, u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")
            # 多少是 avg_uv (全部相同)?
            avg = Vector((sum(us)/len(us), sum(vs)/len(vs)))
            same = sum(1 for uv in bowl_uvs if (uv - avg).length < 1e-6)
            print(f"    均匀UV(avg_uv)占比: {same}/{len(bowl_uvs)} ({same/len(bowl_uvs)*100:.1f}%)")

bm.free()
print("\n=== 诊断完成 ===")
