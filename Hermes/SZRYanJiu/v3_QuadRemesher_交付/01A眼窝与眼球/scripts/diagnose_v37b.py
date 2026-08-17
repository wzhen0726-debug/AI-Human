"""v37 诊断2: 精确检查倒角带法线 + 边界锯齿 + UV纹理连续性.
倒角带 = ring0(皮肤边界)到ring1(碗起始)之间的新面, 位于xz半径 14-17.5mm, y接近rim.
"""
import bpy, bmesh, json, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

# 倒角带面识别: 新创建的quad面, 位于 xz半径 12-18mm, y在 center.y 到 center.y+0.005 之间
# 皮肤面在这个区域也有(三角面), 但倒角带是quad(4边形). 用quad识别新面.
for side, center in [("L", cL), ("R", cR)]:
    print(f"\n=== {side} (center={center.x:.4f},{center.y:.4f},{center.z:.4f}) ===")
    # 倒角带 = quad面, xz 12-18mm, y center.y..center.y+0.006
    chamfer_quads = [f for f in bm.faces
                     if len(f.verts) == 4
                     and center.y < f.calc_center_median().y < center.y + 0.006
                     and 0.010 < (f.calc_center_median()-center).xz.length < 0.019]
    # 碗面 = quad面, y center.y+0.002..center.y+0.02, xz<0.016
    bowl_quads = [f for f in bm.faces
                  if len(f.verts) == 4
                  and center.y + 0.002 < f.calc_center_median().y < center.y + 0.02
                  and (f.calc_center_median()-center).xz.length < 0.016]
    
    if chamfer_quads:
        # 法线朝向: 朝眼球(dot>0) vs 朝外(dot<0)
        toward = sum(1 for f in chamfer_quads if f.normal.dot(center - f.calc_center_median()) > 0)
        away = len(chamfer_quads) - toward
        print(f"倒角带quad: {len(chamfer_quads)} 个, 朝眼球 {toward}, 朝外 {away}")
        # 分桶 (xz半径)
        buckets = {}
        for f in chamfer_quads:
            xz = (f.calc_center_median()-center).xz.length * 1000
            b = int(xz / 1.0)  # 每1mm一桶
            buckets.setdefault(b, [0, 0])
            if f.normal.dot(center - f.calc_center_median()) > 0:
                buckets[b][0] += 1
            else:
                buckets[b][1] += 1
        for b in sorted(buckets):
            t, a = buckets[b]
            print(f"  xz[{b},{b+1}]mm: 朝眼球{t} 朝外{a} (共{t+a})")
    else:
        print("倒角带quad: 无")
    
    if bowl_quads:
        toward = sum(1 for f in bowl_quads if f.normal.dot(center - f.calc_center_median()) > 0)
        print(f"碗面quad: {len(bowl_quads)} 个, 朝眼球 {toward} ({toward/len(bowl_quads)*100:.1f}%)")
    
    # 边界环 jaggedness: 找ring0顶点(皮肤与倒角带交界), 测角度步长均匀性
    # ring0 = 倒角带quad的"外环"顶点, 即xz半径最大且y≈rim的顶点
    rim_v = set()
    for f in chamfer_quads:
        for v in f.verts:
            rim_v.add(v)
    rim_v = [v for v in rim_v if (v.co-center).xz.length > 0.016 and v.co.y < center.y + 0.002]
    if rim_v:
        rim_v.sort(key=lambda v: math.atan2(v.co.z-center.z, v.co.x-center.x))
        # 角度步长
        angles = [math.atan2(v.co.z-center.z, v.co.x-center.x) for v in rim_v]
        # 径向半径
        radii = [(v.co-center).xz.length for v in rim_v]
        # 相邻半径差(局部锯齿度量)
        jumps = [abs(radii[(i+1)%len(radii)] - radii[i]) for i in range(len(radii))]
        print(f"ring0顶点: {len(rim_v)} 个")
        print(f"  径向半径 r=[{min(radii)*1000:.2f},{max(radii)*1000:.2f}]mm, 平均相邻半径跳变={sum(jumps)/len(jumps)*1000:.2f}mm, 最大跳变={max(jumps)*1000:.2f}mm")

bm.free()
print("\n=== 诊断2完成 ===")
