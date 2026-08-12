
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
open_e=[e for e in bm.edges if len(e.link_faces)==1 and near(e.verts[0].co)]
# 环顶点y分布
verts=set()
for e in open_e: verts.add(e.verts[0]); verts.add(e.verts[1])
ys=np.array([v.co.y for v in verts])
print(f"洞口ring0顶点 {len(verts)}: y min={ys.min():.4f} max={ys.max():.4f} 极差={(ys.max()-ys.min())*1000:.1f}mm")
# 侧壁面(连接ring0和bottom_ring): 检查这些面是否扭曲(4顶点不共面)
bpy.ops.object.mode_set(mode='OBJECT')
