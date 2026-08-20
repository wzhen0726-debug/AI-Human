"""L眼4组重复顶点: 精确距离诊断 + 针对性焊接(dist放宽到0.5mm) + 复查."""
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

# ---- 诊断: 打印所有重复对的精确距离 ----
for side in ("L", "R"):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < RAD]
    grid = {}
    for v in lv:
        k = (round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4))
        grid.setdefault(k, []).append(v)
    print(f"=== {side}眼 重复对精确距离 ===")
    dup_verts_all = []
    for k, vs in grid.items():
        if len(vs) > 1:
            dup_verts_all.extend(vs)
            for a in range(len(vs)):
                for b in range(a+1, len(vs)):
                    d = (vs[a].co - vs[b].co).length
                    print(f"  idx={vs[a].index},{vs[b].index} dist={d*1000:.4f}mm "
                          f"co_a={tuple(round(x,6) for x in vs[a].co)} co_b={tuple(round(x,6) for x in vs[b].co)}")
    # 针对性焊接: 只焊这些顶点, dist=0.0005(0.5mm)
    if dup_verts_all:
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=dup_verts_all, dist=0.0005)
        print(f"  焊接(dist=0.5mm): 删除{n0-len(bm.verts)}个顶点")

bm.to_mesh(me)
bm.free()
me.update()
bpy.ops.wm.save_mainfile()
print("Saved:", OUT_BLEND)

# 重开复查
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
    print(f"复查 {side}眼: 顶点={len(lv)} 重复={dups} 游离={loose} 边界边={boundary} 非流形={nonman}")
bm.free()
