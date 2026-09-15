import bpy, os, json, numpy as np, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
print("custom_normal 属性:", "custom_normal" in me.attributes, "| 有 split normals:", me.has_custom_normals if hasattr(me,'has_custom_normals') else '?')
c=Vector((float(J['R']['center'][0]),float(J['R']['center'][1]),float(J['R']['center'][2])))
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.normal_update()
tgt=[]
for f in bm.faces:
    cc=f.calc_center_median()
    if (cc-c).xz.length>0.030 or abs(cc.y-c.y)>0.06: continue
    if f.normal.y>0.05: tgt.append(f)
print(f"R 眼区 法线朝后(>0.05) 面数: {len(tgt)}")
for f in tgt[:3]:
    cc=f.calc_center_median(); print(f"   翻前 normal.y={f.normal.y:.3f} @({cc.x*1000:.1f},{cc.y*1000:.1f},{cc.z*1000:.1f}) area={f.calc_area()*1e6:.3f}mm2")
for f in tgt: f.normal_flip()
bm.normal_update()
n2=sum(1 for f in bm.faces if (f.calc_center_median()-c).xz.length<=0.030 and f.normal.y>0.05)
print(f"bmesh 内翻转后 残留: {n2}")
bm.to_mesh(me); bm.free()
out=os.path.join(D,"_tmp_fliptest.blend"); bpy.ops.wm.save_as_mainfile(filepath=out)
# 重读验证
bpy.ops.wm.open_mainfile(filepath=out)
head2=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm2=bmesh.new(); bm2.from_mesh(head2.data); bm2.faces.ensure_lookup_table(); bm2.normal_update()
n3=sum(1 for f in bm2.faces if (f.calc_center_median()-c).xz.length<=0.030 and f.normal.y>0.05)
print(f"重读后 残留: {n3}  → {'翻转可持久 ✓' if n3==0 else '翻转丢失(存储层问题) ✗'}")
bm2.free()
