"""验证v46i眼窝局部完整性: 焊接/破面/游离点/非流形边/边界边(眼窝rim应缝合高模)."""
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
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

ddfa = json.load(open(DDFA_JSON, encoding="utf-8"))
RAD = 0.030  # 眼中心半径30mm内 = 眼窝+缝合带

for side in ("L", "R"):
    c = Vector(ddfa[side]["center_3d"])
    lv = [v for v in bm.verts if (v.co - c).length < RAD]
    vset = set(v.index for v in lv)

    # 重复顶点: KD-tree精确判定(阈值0.01mm). 教训v46i: 0.1mm网格哈希把碗底
    # 正常相邻顶点(间距0.08mm)误报为重复, 后续误焊导致极点扇74→58三角损坏.
    from mathutils import kdtree
    kd = kdtree.KDTree(len(lv))
    for i, v in enumerate(lv):
        kd.insert(v.co, i)
    kd.balance()
    dup_count = 0
    dup_tagged = 0  # 涉及新结构(v44tag!=0)的重复对
    _tl = bm.faces.layers.int.get("v44tag_" + side)
    seen_pairs = set()
    for i, v in enumerate(lv):
        for co, idx, d in kd.find_range(v.co, 0.00001):
            if idx <= i:
                continue
            if (i, idx) in seen_pairs:
                continue
            seen_pairs.add((i, idx))
            dup_count += 1
            # 归属: 任一顶点属于tag面 → 新结构问题
            if _tl is not None:
                tagged = any(f[_tl] != 0 for f in lv[i].link_faces) or \
                         any(f[_tl] != 0 for f in lv[idx].link_faces)
                if tagged:
                    dup_tagged += 1

    loose = [v for v in lv if not v.link_faces]

    # 局部边: 两端都在区域内
    le = [e for e in bm.edges if e.verts[0].index in vset and e.verts[1].index in vset]
    nonman = [e for e in le if not e.is_boundary and len(e.link_faces) != 2]
    boundary = [e for e in le if e.is_boundary]

    lf = [f for f in bm.faces if all(v.index in vset for v in f.verts)]
    degen = [f for f in lf if f.calc_area() < 1e-12]

    # 极点检测: 只统计link_edges>6的数量与最大值(详细列表太长没意义)
    pole_edges = [len(v.link_edges) for v in lv if len(v.link_edges) > 6]

    # 碗底极点扇完好性: 眼中心径向<0.5mm最深处顶点, 应连M个三角面
    cand = [v for v in lv if Vector((v.co.x-c.x, 0, v.co.z-c.z)).length < 0.0005]
    if cand:
        pole = max(cand, key=lambda v: v.co.y)
        tri_fan = sum(1 for f in pole.link_faces if len(f.verts) == 3)
    else:
        tri_fan = -1

    print(f"=== {side}眼 局部 (中心R={RAD*1000:.0f}mm) ===")
    print(f"  顶点={len(lv)} 边={len(le)} 面={len(lf)}")
    print(f"  重复顶点(精确0.01mm)={dup_count} 其中涉及新结构(tag!=0)={dup_tagged}")
    print(f"  游离点={len(loose)} 退化面={len(degen)}")
    print(f"  非流形边={len(nonman)} 边界边={len(boundary)}")
    print(f"  极点(>6边): {len(pole_edges)}个, 最大={max(pole_edges) if pole_edges else 0}")
    print(f"  碗底极点三角扇: {tri_fan}个三角面")
    if boundary:
        print(f"  !! 边界边示例: {[(round(e.verts[0].co.x,4),round(e.verts[0].co.z,4)) for e in boundary[:3]]}")
bm.free()
