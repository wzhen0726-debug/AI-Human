"""v38 关键几何分析: 眼窝区法线到底应该怎样分布.
坐标: 头前=-Y, 头内=+Y. 眼中心y≈-0.106.
碗面: y在center.y到center.y+0.015, 应该朝眼球(center).
皮肤: y<center.y, 应该朝外(-Y).
倒角带: 在ring0(皮肤)和碗之间, 应连续过渡.
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

for side, center in [("L", cL), ("R", cR)]:
    print(f"\n=== {side}眼 ===")
    # 分桶: xz径向距离(米), 只取眼窝附近(xz<0.022)
    buckets = {}
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if dxz > 0.022 or fc.y < center.y - 0.002:
            continue
        r_mm = int(dxz*1000)
        buckets.setdefault(r_mm, []).append((f, fc))
    for r in sorted(buckets):
        items = buckets[r]
        # 只统计倒角带/碗面区 y>center.y-0.001
        bowl_items = [(f,fc) for f,fc in items if fc.y > center.y - 0.001]
        if not bowl_items: continue
        toward = sum(1 for f,fc in bowl_items if f.normal.dot(center-fc) > 0)
        # 法线y分量统计: -Y(皮肤) vs +Y(头内)
        negY = sum(1 for f,fc in bowl_items if f.normal.y < -0.3)
        posY = sum(1 for f,fc in bowl_items if f.normal.y > 0.3)
        avg = Vector((sum(f.normal.x for f,fc in bowl_items)/len(bowl_items),
                      sum(f.normal.y for f,fc in bowl_items)/len(bowl_items),
                      sum(f.normal.z for f,fc in bowl_items)/len(bowl_items)))
        print(f"  xz{r:2d}mm: {len(bowl_items):3d}面 朝眼球{toward:3d}({toward/len(bowl_items)*100:5.1f}%) "
              f"-Y皮肤向{negY:3d} +Y头内向{posY:3d} avgN=({avg.x:+.2f},{avg.y:+.2f},{avg.z:+.2f})")
bm.free()
