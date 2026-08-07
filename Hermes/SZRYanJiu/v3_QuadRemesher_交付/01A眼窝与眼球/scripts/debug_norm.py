
import bpy, numpy as np, bmesh, json
from mathutils import Vector
OUT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=OUT)
d = json.load(open(DDFA, encoding="utf-8"))
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
mesh = head.data
# 眼窝内的面: 中心在眼睑轮廓多边形内
def pip(x,z,poly):
    inside=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,zi=poly[i]; xj,zj=poly[j]
        if ((zi>z)!=(zj>z)) and (x<(xj-xi)*(z-zi)/(zj-zi)+xi): inside=not inside
        j=i
    return inside
mesh.calc_loop_triangles()
for side in ("L","R"):
    poly=[(r[0],r[2]) for r in d[side]["rim_3d"] if r]
    center=np.array([r for r in d[side]["rim_3d"] if r]).mean(0)
    # 碗内面: 面心在多边形内 且 y>center.y(碗内凹)
    norms=[]
    for f in mesh.polygons:
        fc=np.array(f.center[:])
        if pip(fc[0],fc[2],poly):
            norms.append(np.array(f.normal[:]))
    norms=np.array(norms)
    if len(norms):
        ny=norms[:,1]
        print(f"=== {side}眼窝内 {len(norms)}面 ===")
        print(f"  法线y: mean={ny.mean():.3f} | 朝外(-Y,正常)={int((ny<-0.2).sum())} 朝内(+Y,反)={int((ny>0.2).sum())} 侧向={int((abs(ny)<=0.2).sum())}")
