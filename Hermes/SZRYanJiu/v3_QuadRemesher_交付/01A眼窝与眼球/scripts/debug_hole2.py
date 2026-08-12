
import bpy, numpy as np, bmesh, json
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\01_highpoly_repair.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
# 只做删面(不开碗), 看洞的边界环有多少点、分布
bpy.ops.wm.open_mainfile(filepath=SOCKET)
d = json.load(open(EYELID, encoding="utf-8"))
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
import sys; sys.path.insert(0, r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\scripts")
from socket_ops import load_eyelid_contour, point_in_polygon
poly = load_eyelid_contour("L")
c = np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(obj.data)
bm.faces.ensure_lookup_table()
to_del=[f for f in bm.faces if point_in_polygon(f.calc_center_median().x, f.calc_center_median().z, poly) and f.calc_center_median().y < c[1]+0.005]
bmesh.ops.delete(bm, geom=to_del, context='FACES')
bmesh.update_edit_mesh(obj.data)
bm.edges.ensure_lookup_table()
# 删面后的开放边
open_e=[e for e in bm.edges if len(e.link_faces)==1]
# 开放边顶点距轮廓的距离分布
dists=[]
for e in open_e:
    m=(e.verts[0].co+e.verts[1].co)/2
    # 到多边形边界距离
    best=1e9
    for i in range(len(poly)):
        x1,z1=poly[i]; x2,z2=poly[(i+1)%len(poly)]
        ex,ez=x2-x1,z2-z1; L2=ex*ex+ez*ez
        t=0 if L2<1e-12 else max(0,min(1,((m.x-x1)*ex+(m.z-z1)*ez)/L2))
        qx,qz=x1+t*ex,z1+t*ez
        best=min(best,((m.x-qx)**2+(m.z-qz)**2)**0.5)
    dists.append(best*1000)
dists=np.array(dists)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"删面{len(to_del)}面, 开放边{len(open_e)}条")
print(f"开放边到轮廓距离: min={dists.min():.1f} max={dists.max():.1f} mean={dists.mean():.1f}mm")
print(f"  <2mm(贴轮廓): {(dists<2).sum()}, 2-5mm: {((dists>=2)&(dists<5)).sum()}, >5mm(远,碎边): {(dists>=5).sum()}")
