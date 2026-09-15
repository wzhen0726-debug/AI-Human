# 独立面朝向判据: 正视(-Y)相机下, 面法线 y>0 = 朝屏幕里 = 反面(红)
import bpy, os, json, numpy as np, bmesh, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
_d=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
if bpy.context.mode!='OBJECT':
    bpy.context.view_layer.objects.active=head; bpy.ops.object.mode_set(mode='OBJECT')
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
for side in ("L","R"):
    c=_d[side]["center_3d"]; cv=Vector((float(c[0]),float(c[1]),float(c[2])))
    # 只统计"眼周 1.5~8mm 环带"(rim 外那圈) 的面
    cnt=0; back=0
    for f in bm.faces:
        cc=f.calc_center_median()
        d=(cc-cv).xz.length
        if not (0.0015<d<0.008) or cc.y>cv.y-0.002: continue
        cnt+=1
        if f.normal.y>0.0: back+=1
    print(f"{side}: rim 外环带(d=1.5~8mm) 面 {cnt}, 其中法线朝里(y>0)=红 {back} ({100.0*back/max(1,cnt):.1f}%)")
bm.free()
