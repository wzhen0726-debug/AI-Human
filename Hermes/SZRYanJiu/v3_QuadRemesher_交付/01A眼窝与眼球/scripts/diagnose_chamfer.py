"""v38 判据验证: 倒角带正确朝向到底是什么?
分析倒角带每个面的位置 vs 正确法线方向.
- 皮肤面(ring0外侧): 法线朝外(-Y)
- 碗内壁(碗底): 法线朝眼球(center)
- 倒角带(ring0→碗): 法线应连续过渡, 从-Y渐变到朝眼球

关键: 倒角带面法线应该大致朝外(-Y)还是朝眼球?
答案: 倒角带是皮肤到碗的坡道, 它的"外侧"应该可见, 所以法线应朝外(-Y偏眼球方向).
如果倒角带法线朝+Y(头内), 那就是反向(用户看到的黑色).
"""
import bpy, bmesh, json, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new(); bm.from_mesh(obj.data); bm.faces.ensure_lookup_table()

# 分析倒角带: 新创建的quad面, 位于ring0和碗之间
# 识别: quad面, y在center.y-0.002到center.y+0.006, xz 14-20mm
for side, center in [("L", cL), ("R", cR)]:
    print(f"\n=== {side}眼 倒角带分析 ===")
    chamfer = []
    for f in bm.faces:
        if len(f.verts) != 4: continue
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if not (0.013 < dxz < 0.021): continue
        if not (center.y - 0.002 < fc.y < center.y + 0.006): continue
        chamfer.append(f)
    print(f"倒角带quad: {len(chamfer)}个")
    if chamfer:
        # 当前法线分布
        toward_eye = sum(1 for f in chamfer if f.normal.dot(center - f.calc_center_median()) > 0)
        outward = sum(1 for f in chamfer if f.normal.y < -0.3)
        inward = sum(1 for f in chamfer if f.normal.y > 0.3)
        print(f"  当前: 朝眼球{toward_eye}({toward_eye/len(chamfer)*100:.1f}%) 朝外-Y{outward} 朝内+Y{inward}")
        # 正确朝向: 倒角带应朝外(-Y为主), 即normal.y应该<0
        # 如果normal.y>0, 说明朝头内=反向
        wrong = [f for f in chamfer if f.normal.y > 0.1]
        print(f"  反向面(normal.y>0.1, 朝头内): {len(wrong)}个")
        # 这些反向面的xz分布
        for f in wrong[:5]:
            fc = f.calc_center_median()
            dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
            print(f"    反向面 @xz={dxz*1000:.1f}mm y={fc.y:.4f} normal=({f.normal.x:.2f},{f.normal.y:.2f},{f.normal.z:.2f})")

bm.free()
