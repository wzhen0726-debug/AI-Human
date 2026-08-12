
import bpy, numpy as np, bmesh, json
REPAIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\01_highpoly_repair.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
import sys; sys.path.insert(0, r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\scripts")
from socket_ops import load_eyelid_contour, point_in_polygon
bpy.ops.wm.open_mainfile(filepath=REPAIR)
d = json.load(open(EYELID, encoding="utf-8"))
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
poly = load_eyelid_contour("L")
c = np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(obj.data)
bm.faces.ensure_lookup_table()
# 删面(同make_eye_socket)
to_del=[f for f in bm.faces if point_in_polygon(f.calc_center_median().x, f.calc_center_median().z, poly) and f.calc_center_median().y < c[1]+0.005]
bmesh.ops.delete(bm, geom=to_del, context='FACES')
bmesh.update_edit_mesh(obj.data)
bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
# 拓扑法找边界环: 从一条开放边出发, 沿开放边走闭环
def is_open(e): return len(e.link_faces)==1
open_edges=[e for e in bm.edges if is_open(e)]
# 建顶点->开放边映射
from collections import defaultdict
v2e=defaultdict(list)
for e in open_edges:
    v2e[e.verts[0].index].append(e); v2e[e.verts[1].index].append(e)
# 找眼窝附近的开放边起点
def near(v): return np.hypot(v.co.x-c[0], v.co.z-c[2])<0.020
start=[e for e in open_edges if near(e.verts[0].co)]
print(f"删面{len(to_del)}面, 总开放边{len(open_edges)}, 眼窝附近{len(start)}")
if start:
    # 沿闭环走
    loop=[]; e=start[0]; v=e.verts[0]; prev_v=None; first_v=v
    for _ in range(500):
        loop.append(v.index)
        # 找v的下一条开放边(非来路)
        nxt=[x for x in v2e[v.index] if is_open(x)]
        nxt_v=None
        for x in nxt:
            ov = x.verts[1] if x.verts[0].index==v.index else x.verts[0]
            if prev_v is None or ov.index!=prev_v.index:
                if ov.index==first_v.index and len(loop)>2: nxt_v=ov; break
                nxt_v=ov; break
        if nxt_v is None or nxt_v.index==first_v.index: break
        prev_v=v; v=nxt_v
    print(f"拓扑闭环走得 {len(loop)} 顶点 (真边界环)")
    # 这些顶点的y分布
    bm.verts.ensure_lookup_table()
    ys=[bm.verts[i].co.y for i in loop]
    print(f"  边界环顶点y: {min(ys):.4f}~{max(ys):.4f} 极差{(max(ys)-min(ys))*1000:.1f}mm")
bpy.ops.object.mode_set(mode='OBJECT')
