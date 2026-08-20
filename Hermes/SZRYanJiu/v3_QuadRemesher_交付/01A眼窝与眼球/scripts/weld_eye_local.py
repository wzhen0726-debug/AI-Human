"""v46i焊接修复(重跑): 局部remove_doubles → to_mesh → save → 重开复查."""
import bpy, os, sys, json, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
me = obj.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
RAD = 0.030
total_removed = 0
for side in ("L", "R"):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < RAD]
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=lv, dist=0.0001)
    removed = n0 - len(bm.verts)
    total_removed += removed
    print(f"{side}眼 焊接: 删除{removed}个重复顶点")

bm.to_mesh(me)
bm.free()
me.update()
bpy.ops.wm.save_mainfile()
print("Saved:", OUT_BLEND)

# 重开复查(确保落盘数据)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
me = obj.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
for side in ("L", "R"):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < RAD]
    grid = {}
    for v in lv:
        k = (round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4))
        grid.setdefault(k, []).append(v)
    dups = sum(len(vs)-1 for vs in grid.values() if len(vs) > 1)
    loose = sum(1 for v in lv if not v.link_faces)
    vset = set(v.index for v in lv)
    le = [e for e in bm.edges if e.verts[0].index in vset and e.verts[1].index in vset]
    boundary = sum(1 for e in le if e.is_boundary)
    nonman = sum(1 for e in le if not e.is_boundary and len(e.link_faces) != 2)
    lf = [f for f in bm.faces if all(v.index in vset for v in f.verts)]
    degen = sum(1 for f in lf if f.calc_area() < 1e-12)
    print(f"复查 {side}眼: 顶点={len(lv)} 重复={dups} 游离={loose} 边界边={boundary} 非流形={nonman} 退化面={degen}")
bm.free()
print(f"总删除重复顶点: {total_removed}")
