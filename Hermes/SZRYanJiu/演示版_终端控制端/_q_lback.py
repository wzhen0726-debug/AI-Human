import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table(); bm.normal_update()
for side in ("L","R"):
    P=np.array([[float(p[0]),float(p[2])] for p in J[side]["rim_3d"]])
    bad=[]
    for f in bm.faces:
        c=f.calc_center_median()
        if abs(c.y-(-0.106))>0.06: continue
        d=np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min()
        if d>0.008: continue
        if f.normal.y>0.05:
            bad.append((d*1000, f.calc_area()*1e6, c))
    print(f"{side}: rim 8mm 内朝后的面 {len(bad)}")
    bad.sort()
    for d,a,c in bad[:10]:
        print(f"   距轮廓{d:.2f}mm 面积{a:.4f}mm² y{c.y*1000:.1f} dx{(c.x-float(J[side]['center'][0]))*1000:+.2f} dz{(c.z-float(J[side]['center'][2]))*1000:+.2f}")
bm.free()
