import bpy, os, json, numpy as np, bmesh, sys
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
F=sys.argv[-1] if sys.argv[-1].endswith(".blend") else os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend")
bpy.ops.wm.open_mainfile(filepath=F)
print("文件:", os.path.basename(F))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
for side in ("L","R"):
    c=_d[side]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    bins=[(0.0,0.0015,"环上0~1.5mm"),(0.0015,0.003,"1.5~3mm"),(0.003,0.008,"3~8mm"),(0.008,0.020,"8~20mm")]
    out=[]
    for lo,hi,nm in bins:
        cnt=0;back=0
        for f in bm.faces:
            cc=f.calc_center_median()
            d=(cc-cv).xz.length
            if not (lo<=d<hi) or cc.y>cv.y-0.002: continue
            cnt+=1
            if f.normal.y>0.0: back+=1
        out.append(f"{nm}: {back}/{cnt}红")
    print(f"  {side}: " + " | ".join(out))
bm.free()
