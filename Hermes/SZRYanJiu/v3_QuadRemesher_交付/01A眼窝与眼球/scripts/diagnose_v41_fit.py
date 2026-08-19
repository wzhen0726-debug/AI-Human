"""diagnose_v41_fit: rim收小后开口与输入模型眼睑的匹配度
问题: 用户说开口不符合眼睑, 且着色模式眼周有锯齿/破损
诊断: 1) 输入模型眼睑开口的实际范围(开放边/锐利边)
      2) 我们rim的实际范围
      3) 两者偏差
"""
import bpy, os, sys, json, math
from mathutils import Vector
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def get_input_eye_opening(filepath, label):
    """输入模型眼睑开口边界"""
    bpy.ops.wm.open_mainfile(filepath=filepath)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for side, center in [("L", cL), ("R", cR)]:
        # 找眼周开放边
        open_edges = []
        for e in bm.edges:
            if len(e.link_faces) == 1:
                ec = (e.verts[0].co + e.verts[1].co) / 2
                dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
                if dxz < 0.030:
                    open_edges.append((ec, dxz))
        if open_edges:
            xs = [ec.x for ec, _ in open_edges]
            zs = [ec.z for ec, _ in open_edges]
            dxzs = [d for _, d in open_edges]
            print(f"  {label} {side}: 开放边={len(open_edges)}, "
                  f"x范围={(min(xs)-center.x)*1000:.1f}~{(max(xs)-center.x)*1000:.1f}mm "
                  f"z范围={(min(zs)-center.z)*1000:.1f}~{(max(zs)-center.z)*1000:.1f}mm "
                  f"半径范围{min(dxzs)*1000:.1f}~{max(dxzs)*1000:.1f}mm")
        else:
            print(f"  {label} {side}: 无开放边")
    bm.free()

print("=== 输入模型眼睑开口 ===")
get_input_eye_opening(IN_BLEND, "输入")

print("\n=== v41输出 rim边界 ===")
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])
import bmesh
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.edges.ensure_lookup_table()
for side, center in [("L", cL), ("R", cR)]:
    open_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            ec = (e.verts[0].co + e.verts[1].co) / 2
            dxz = math.sqrt((ec.x-center.x)**2 + (ec.z-center.z)**2)
            if dxz < 0.030:
                open_edges.append((ec, dxz))
    if open_edges:
        xs = [ec.x for ec, _ in open_edges]
        zs = [ec.z for ec, _ in open_edges]
        dxzs = [d for _, d in open_edges]
        print(f"  输出 {side}: 开放边={len(open_edges)}, "
              f"x范围={(min(xs)-center.x)*1000:.1f}~{(max(xs)-center.x)*1000:.1f}mm "
              f"z范围={(min(zs)-center.z)*1000:.1f}~{(max(zs)-center.z)*1000:.1f}mm "
              f"半径范围{min(dxzs)*1000:.1f}~{max(dxzs)*1000:.1f}mm")
bm.free()

print("\n诊断完成")
