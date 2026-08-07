
import bpy, numpy as np, json
from mathutils import Vector
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_2_eyeball_placed.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
bpy.ops.wm.open_mainfile(filepath=OUT)
d = json.load(open(DDFA, encoding="utf-8"))
eyes = [o for o in bpy.data.objects if o.type=='MESH' and 'Eye' in o.name]
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))

# 1) 眼球位置: 球心 vs 眼窝开口中心(开孔环)
for side in ("L","R"):
    c3 = np.array(d[side]["center_3d"])
    eye = next(o for o in eyes if (o.location.x<0)==(side=="L"))
    ec = np.array(eye.location[:])
    # 眼窝开口中心(开孔环顶点均值)
    nv=len(head.data.vertices); V=np.empty(nv*3,dtype=np.float32)
    head.data.vertices.foreach_get("co",V); V=V.reshape(nv,3).astype(np.float64)
    dx=(V[:,0]-c3[0])/0.013; dz=(V[:,2]-c3[2])/0.009; r2=dx*dx+dz*dz
    ring = V[(r2>=0.8)&(r2<=1.2)]
    ring_c = ring.mean(0) if len(ring) else c3
    print(f"=== {side}: 眼球心={np.round(ec,4)} 眼窝开口中心={np.round(ring_c,4)} ===")
    print(f"  偏移: dx={(ec[0]-ring_c[0])*1000:+.1f} dy={(ec[1]-ring_c[1])*1000:+.1f}(负=更前/更外) dz={(ec[2]-ring_c[2])*1000:+.1f}mm")
    print(f"  角膜前极y={ec[1]-0.0145:.4f} vs 眼窝口y={ring_c[1]:.4f}: 前极比口前{(ring_c[1]-(ec[1]-0.0145))*1000:+.1f}mm")

# 2) 眼窝面朝向: 眼窝内壁面的法线方向(应朝-Y=朝外/朝眼球)
import bmesh
bpy.context.view_layer.objects.active = head
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(head.data)
bm.faces.ensure_lookup_table()
c3 = np.array(d["L"]["center_3d"])
# 取眼窝内壁的面(开口椭圆内, y在角膜点后方=碗内)
dx=(np.array([v.co for v in bm.verts])[:,0]-c3[0])/0.013 if False else None
# 简单: 找开口附近的面, 算法线
cup_faces = []
for f in bm.faces:
    fc = f.calc_center_median()
    ddx=(fc.x-c3[0])/0.013; ddz=(fc.z-c3[2])/0.009
    if ddx*ddx+ddz*ddz < 0.8 and fc.y > c3[1]-0.002:  # 碗内面
        cup_faces.append(f)
bpy.ops.object.mode_set(mode='OBJECT')
if cup_faces:
    normals = np.array([f.normal[:] for f in cup_faces])
    ny = normals[:,1]
    print(f"=== 左眼窝内壁 {len(cup_faces)}面 法线y分量: mean={ny.mean():.3f} ===")
    print(f"  朝外(-Y,正常)的面: {(ny<-0.3).sum()}, 朝内(+Y,反了)的面: {(ny>0.3).sum()}")
