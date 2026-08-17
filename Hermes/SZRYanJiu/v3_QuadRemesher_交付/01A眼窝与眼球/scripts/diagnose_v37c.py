"""验证v35的recalc是否翻了皮肤面: 对比v35产物中眼区皮肤面的法线朝向.
如果v35的recalc没翻皮肤面, 说明ref(皮肤)+bowl混合时recalc以皮肤为种子, 
但bowl面被强制同向(朝外)——这与几何兜底的"碗面必须朝眼球"矛盾,
所以几何兜底又把碗面翻回去. 净效果=碗面朝眼球+皮肤面不受影响.
"""
import bpy, bmesh, json, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

# 加载v35产物 (当前OUT_BLEND是v37, 先备份, 用v35的)
# 从git历史看, v35 blend是2092278生成的, 但.blend不入git.
# 用当前blend (v37) 检查即可——v37也有restore步骤, 关键是看restore之前的状态.
# 但当前blend已经restore过了. 改方案: 直接分析v35代码逻辑 + 用当前blend验证眼区皮肤面.

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
bm.faces.ensure_lookup_table()

# v35的restore条件: y<center.y, xz<0.025, normal.y>0.1 (翻向-Y=朝内)
# 检查这些面在restore后的状态: 如果它们现在朝外(normal.y<0), 说明restore把它们翻回来了
for side, center in [("L", cL), ("R", cR)]:
    skin_near_eye = [f for f in bm.faces
                     if f.calc_center_median().y < center.y
                     and (f.calc_center_median() - center).xz.length < 0.025]
    inward = [f for f in skin_near_eye if f.normal.y > 0.1]
    print(f"{side}: 眼区皮肤面(y<center.y, xz<25mm) = {len(skin_near_eye)}, 朝内={len(inward)}")
    # 这些朝内面的分布
    if inward:
        xz_ranges = [(f.calc_center_median()-center).xz.length*1000 for f in inward]
        print(f"  朝内面xz分布: min={min(xz_ranges):.1f} max={max(xz_ranges):.1f}mm")
        # 按距离分桶
        for lo, hi in [(0,5),(5,10),(10,15),(15,20),(20,25)]:
            cnt = sum(1 for x in xz_ranges if lo <= x < hi)
            if cnt: print(f"    xz[{lo},{hi}]mm: {cnt}面")

# 检查碗面: v35几何兜底条件 y>center.y, y<center.y+0.02, xz<0.014
# v37扩展到xz<0.019. 检查当前bowl面朝向
for side, center in [("L", cL), ("R", cR)]:
    bowl = [f for f in bm.faces
            if center.y < f.calc_center_median().y < center.y + 0.02
            and (f.calc_center_median() - center).xz.length < 0.019]
    toward = sum(1 for f in bowl if f.normal.dot(center - f.calc_center_median()) > 0)
    print(f"{side}: 碗面+倒角带 = {len(bowl)}, 朝眼球={toward} ({toward/len(bowl)*100:.1f}%)")

bm.free()
