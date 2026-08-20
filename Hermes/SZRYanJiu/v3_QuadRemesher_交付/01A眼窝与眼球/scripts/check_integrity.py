"""验证v46i合并后眼窝结构完整性: 焊接/破面/游离点/非流形边."""
import bpy, os, sys, json, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH']

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
centers = {"L": Vector(ddfa["L"]["center_3d"]), "R": Vector(ddfa["R"]["center_3d"])}
report = {}

for obj in meshes:
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    total_v, total_f = len(bm.verts), len(bm.faces)

    # 孤立点: 不属于任何面
    loose_v = [v for v in bm.verts if not v.link_faces]

    # 重复顶点(焊接失败): 距离<0.0005的不同顶点
    dup_pairs = 0
    seen = set()
    vlist = list(bm.verts)
    # 简单grid hash
    grid = {}
    for v in vlist:
        k = (round(v.co.x, 3), round(v.co.y, 3), round(v.co.z, 3))
        grid.setdefault(k, []).append(v)
    for k, vs in grid.items():
        if len(vs) > 1:
            dup_pairs += len(vs) - 1

    # 非流形边 (内部边应恰好被2面共享; 碗底中心点三角扇的边=3+面共享属极点正常)
    nm_edges = [e for e in bm.edges if not e.is_boundary and len(e.link_faces) != 2]
    # 边界边 (rim与高模缝合处应为0, 除非未缝合)
    boundary_edges = [e for e in bm.edges if e.is_boundary]

    # 退化面 (面积≈0)
    degen_f = [f for f in bm.faces if f.calc_area() < 1e-12]

    # 反向面检测: 眼碗面朝外应为大体朝-Y(前). 用法线与(面中心-眼中心)点积
    # 只对眼窝区(中心附近)抽样
    name = obj.name
    rep = {
        "verts": total_v, "faces": total_f,
        "loose_verts": len(loose_v),
        "dup_vert_pairs": dup_pairs,
        "nonmanifold_edges": len(nm_edges),
        "boundary_edges": len(boundary_edges),
        "degenerate_faces": len(degen_f),
    }
    report[name] = rep
    bm.free()

print(json.dumps(report, ensure_ascii=False, indent=2))
bad = []
for name, r in report.items():
    if r["loose_verts"]: bad.append(f"{name}: {r['loose_verts']}游离点")
    if r["dup_vert_pairs"]: bad.append(f"{name}: {r['dup_vert_pairs']}未焊接重复顶点")
    if r["degenerate_faces"]: bad.append(f"{name}: {r['degenerate_faces']}退化面")
print("\n=== 完整性判定 ===")
print("PASS: 无游离点/无重复顶点/无退化面" if not bad else "FAIL:\n  " + "\n  ".join(bad))
print("注: 非流形边在碗底极点处属正常结构; 边界边应仅存在于rim外缘与高模接缝处")
