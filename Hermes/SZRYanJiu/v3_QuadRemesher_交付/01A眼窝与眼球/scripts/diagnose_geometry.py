"""v38 几何分析: 倒角带每个面的"朝眼球"dot vs "合理朝向"dot, 理解什么才是正确朝向.
倒角带是皮肤到碗的过渡坡道, 它的法线应该介于皮肤法线和碗面法线之间.
- 皮肤面法线: 朝脸外(-Y)
- 碗内壁法线: 朝眼球中心
- 倒角带法线: 应该连续过渡, 既不是纯-Y也不是纯朝眼球

关键问题: 倒角带边缘环(靠近ring0)的面, 如果用"朝眼球"判据,
因为眼球中心在这些面的"后上方", dot可能为负, 被误判为反向而翻转,
翻转后反而朝向头内(+Y)=真正的反向.
"""
import bpy, bmesh, json, os, sys
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

bm = bmesh.new(); bm.from_mesh(me)
bm.faces.ensure_lookup_table()

# 对每个眼, 分析不同径向环带的面法线分布
import math
for side, center in [("L", cL)]:
    print(f"\n=== {side} 眼, 径向环带法线分析 ===")
    print(f"眼中心: x={center.x:.4f} y={center.y:.4f} z={center.z:.4f}")
    # 按xz半径分桶, 看每个环带的面法线
    buckets = {}
    for f in bm.faces:
        fc = f.calc_center_median()
        d = center - fc
        xz = math.sqrt(d.x**2 + d.z**2)
        # 只看眼窝区 (y在碗区范围)
        if not (center.y - 0.002 < fc.y < center.y + 0.02):
            continue
        r = int(xz * 1000 / 2) * 2  # 每2mm一桶
        buckets.setdefault(r, []).append(f)
    for r in sorted(buckets):
        faces = buckets[r]
        # 每个面: 法线, 朝眼球dot, 法线y分量
        toward = sum(1 for f in faces if f.normal.dot(center - f.calc_center_median()) > 0)
        # 法线朝外(-Y, 像皮肤)的比例
        outward = sum(1 for f in faces if f.normal.y < -0.3)
        # 法线朝内(+Y, 朝头内)的比例
        inward = sum(1 for f in faces if f.normal.y > 0.3)
        # 平均法线
        avg_n = Vector((sum(f.normal.x for f in faces)/len(faces),
                        sum(f.normal.y for f in faces)/len(faces),
                        sum(f.normal.z for f in faces)/len(faces)))
        print(f"  xz{r:2d}-{r+2:2d}mm: {len(faces):4d}面 朝眼球{toward:4d}({toward/len(faces)*100:5.1f}%) "
              f"朝外-Y{outward:4d} 朝内+Y{inward:4d} | 平均法线=({avg_n.x:+.2f},{avg_n.y:+.2f},{avg_n.z:+.2f})")

bm.free()
