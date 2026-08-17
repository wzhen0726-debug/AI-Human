"""对比输入模型 vs 输出的 front_inward 面数, 定位 +575 来源."""
import bpy, bmesh, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def count_front_inward(blend_path, label):
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    me = obj.data
    # 删custom_normal(与管线一致)
    attr = me.attributes.get('custom_normal')
    if attr:
        me.attributes.remove(attr)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    fi = [f for f in bm.faces
          if f.normal.y > 0.1 and f.calc_center_median().y < 0
          and abs(f.calc_center_median().x) < 0.08
          and 1.5 < f.calc_center_median().z < 1.75]
    print(f"{label}: front_inward={len(fi)}")
    # 分布: 靠近眼区(xz<0.025) vs 远处
    def load_3ddfa():
        import json
        with open(DDFA_JSON, encoding="utf-8") as f:
            d = json.load(f)
        return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
    cL, cR = load_3ddfa()
    near = 0; far = 0
    for f in fi:
        fc = f.calc_center_median()
        dL = (fc - cL).xz.length; dR = (fc - cR).xz.length
        if min(dL, dR) < 0.025:
            near += 1
        else:
            far += 1
    print(f"  其中眼区附近(xz<25mm): {near}, 远处: {far}")
    bm.free()

count_front_inward(IN_BLEND, "输入模型")
count_front_inward(OUT_BLEND, "输出模型")
