"""v38 统一判据验证: 眼窝所有面(碗+倒角带)法线应该朝-Y(朝头前/观察者).
这是正确的几何: 眼窝是凹陷, 从前面看进去, 可见面的法线都朝-Y.
测试: 如果用normal.y<0作为"正确"判据, 当前模型有多少面是错的?
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
    # 眼窝区所有新面(碗+倒角带): y>center.y, xz<0.021
    socket_faces = []
    for f in bm.faces:
        fc = f.calc_center_median()
        dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
        if center.y < fc.y < center.y + 0.02 and dxz < 0.021:
            socket_faces.append(f)
    print(f"眼窝区面(碗+倒角带): {len(socket_faces)}个")
    # 用-Y判据: 法线应朝头前(normal.y<0)
    correct_Y = sum(1 for f in socket_faces if f.normal.y < 0)
    wrong_Y = [f for f in socket_faces if f.normal.y > 0]
    print(f"  -Y判据(朝头前): 正确{correct_Y}({correct_Y/len(socket_faces)*100:.1f}%) 反向{len(wrong_Y)}")
    # 用朝眼球判据对比
    toward_eye = sum(1 for f in socket_faces if f.normal.dot(center - f.calc_center_median()) > 0)
    print(f"  朝眼球判据: {toward_eye}({toward_eye/len(socket_faces)*100:.1f}%)")
    # 反向面分布(按xz)
    if wrong_Y:
        print(f"  反向面(normal.y>0) xz分布:")
        xz_count = {}
        for f in wrong_Y:
            fc = f.calc_center_median()
            dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2) * 1000
            r = int(dxz)
            xz_count[r] = xz_count.get(r, 0) + 1
        for r in sorted(xz_count):
            print(f"    xz{r:2d}mm: {xz_count[r]}个")
bm.free()
