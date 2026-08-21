"""诊断eye002(Blender内): 输出对象状态+虹膜UV范围+眼珠vs开口中心偏移.
输出uv范围供diag_eye002_pupil.py(PIL)使用."""
import bpy, os, sys, json
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import OUT_BLEND, DDFA_JSON
from eye002_config import EYE002_BLEND
from eye_socket_config import EYELID_CONTOUR_JSON

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
print("=== 输出blend中Eye002对象 ===")
for o in bpy.data.objects:
    if o.name.startswith("Eye002") or o.name == "Eye1":
        print(f"  {o.name!r} type={o.type} loc={[round(x,4) for x in o.location]} "
              f"parent={o.parent.name if o.parent else None}")
        if o.type == 'MESH':
            V = [o.matrix_world @ v.co for v in o.data.vertices]
            c = sum(V, Vector((0,0,0))) / len(V)
            print(f"      verts={len(o.data.vertices)} 几何中心={[round(x,4) for x in c]}")

bpy.ops.wm.open_mainfile(filepath=EYE002_BLEND)
iri = bpy.data.objects["Eye_Iris"]
uvl = iri.data.uv_layers.active
us, vs = [], []
for poly in iri.data.polygons:
    for li in poly.loop_indices:
        uv = uvl.data[li].uv
        us.append(uv.x); vs.append(uv.y)
umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
print(f"\n=== 虹膜UV范围 ===")
print(f"  u:[{umin:.4f},{umax:.4f}] v:[{vmin:.4f},{vmax:.4f}] 中心=({(umin+umax)/2:.4f},{(vmin+vmax)/2:.4f})")

cont = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
print(f"\n=== 眼珠x/z vs 眼睑开口中心 ===")
for side in ("L", "R"):
    c_open = cont[side]["center"]   # 手动标记轮廓中心
    c_eye = ddfa[side]["center_3d"]
    print(f"  {side}: 开口中心=({c_open[0]:.4f},{c_open[2]:.4f}) 眼珠x/z=({c_eye[0]:.4f},{c_eye[2]:.4f}) "
          f"偏移dx={(c_eye[0]-c_open[0])*1000:+.2f}mm dz={(c_eye[2]-c_open[2])*1000:+.2f}mm")
# 输出uv给PIL脚本
json.dump({"umin": umin, "umax": umax, "vmin": vmin, "vmax": vmax},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "iris_uv_range.json"), "w"))
