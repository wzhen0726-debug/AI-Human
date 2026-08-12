
import bpy, numpy as np, bmesh, json
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=SOCKET)
d = json.load(open(EYELID, encoding="utf-8"))
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
c = np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
bpy.context.view_layer.objects.active = head
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(head.data)
bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
def near(v): return np.hypot(v.x-c[0], v.z-c[2])<0.020
# 真实开放边环(洞口)
open_e=[e for e in bm.edges if len(e.link_faces)==1 and near(e.verts[0].co)]
ring_verts=set()
for e in open_e: ring_verts.add(e.verts[0].index); ring_verts.add(e.verts[1].index)
print(f"洞口真实开放边: {len(open_e)}条边, {len(ring_verts)}顶点")
# 这些顶点现在连着几个面? (1面=真边界, 2面=内部被焊接)
multi=0
for e in open_e:
    pass
# 检查洞口环顶点是否也和碗面共享: 找碗底环(最深处顶点)
ys=[(e.verts[0].co.y+e.verts[1].co.y)/2 for e in open_e]
print(f"  洞口环顶点y: {min(ys):.4f}~{max(ys):.4f}")
# 碗底环顶点(最深处y最大的顶点, 在洞内)
allv=[v for v in bm.verts if near(v.co) and len(v.link_faces)>0]
if allv:
    ymax=max(v.co.y for v in allv)
    deep=[v for v in allv if v.co.y > ymax-0.002]
    print(f"  碗内最深顶点(y≈{ymax:.4f}): {len(deep)}个, 各连{len(deep[0].link_faces) if deep else 0}面")
bpy.ops.object.mode_set(mode='OBJECT')
