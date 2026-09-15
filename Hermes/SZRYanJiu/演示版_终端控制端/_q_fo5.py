# 区分: 眼周反面在【轮廓内(洞口里=正常)】还是【轮廓外(皮肤上=错)】
import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.normal_update()
def inpoly(x,z,P):
    c=False; n=len(P)
    for i in range(n):
        x1,z1=P[i]; x2,z2=P[(i+1)%n]
        if ((z1>z)!=(z2>z)) and (x<(x2-x1)*(z-z1)/(z2-z1+1e-30)+x1): c=not c
    return c
for side in ("L","R"):
    c=Vector((float(J[side]['center'][0]),float(J[side]['center'][1]),float(J[side]['center'][2])))
    P=np.array([[float(p[0]),float(p[2])] for p in J[side]['rim_3d']])
    Pl=[tuple(map(float,[p[0],p[2]])) for p in J[side]['rim_3d']]
    o_in=0; o_out=0; det=[]
    for f in bm.faces:
        cc=f.calc_center_median()
        if (cc-c).xz.length>0.030 or abs(cc.y-c.y)>0.06: continue
        d=float(np.sqrt((P[:,0]-cc.x)**2+(P[:,1]-cc.z)**2).min())
        if d>0.008: continue
        if f.normal.y>0.0:
            if inpoly(cc.x,cc.z,Pl): o_in+=1
            else:
                o_out+=1; det.append((d,cc.copy(),f.normal.y))
    print(f"{side}: 眼周8mm内反面 轮廓内(正常) {o_in} | 轮廓外(皮肤上=错) {o_out}")
    for d,cc,ny in sorted(det,reverse=True)[:5]:
        print(f"    皮肤反面 距轮廓{d*1000:.2f}mm @({cc.x*1000:.1f},{cc.y*1000:.1f},{cc.z*1000:.1f}) normal.y={ny:.3f}")
bm.free()
