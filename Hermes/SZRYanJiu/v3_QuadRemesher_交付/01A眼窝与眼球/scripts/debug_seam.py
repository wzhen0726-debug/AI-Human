
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
bm.edges.ensure_lookup_table()
# 找碗口边界环(ring0): 压凹深度处(y≈rim_y+max_depth)的开放边
# 先看有多少开放边, 以及碗底环
open_e=[e for e in bm.edges if len(e.link_faces)==1]
# 眼窝附近的开放边
def near(v): return np.hypot(v.x-c[0], v.z-c[2])<0.020
socket_open=[e for e in open_e if near(e.verts[0].co)]
print(f"眼窝附近开放边: {len(socket_open)}")
if socket_open:
    ys=[ (e.verts[0].co.y+e.verts[1].co.y)/2 for e in socket_open]
    print(f"  开放边y范围: {min(ys):.4f}~{max(ys):.4f} (脸表面y≈-0.10, 碗底y≈-0.087)")
# 检查碗内是否有未连接的自由面
bpy.ops.object.mode_set(mode='OBJECT')
