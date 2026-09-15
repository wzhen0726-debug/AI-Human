import bpy, os, json
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
print("对象:", head.name, "| 面数", len(me.polygons))
print("材质槽:", [(i,m.name if m else None) for i,m in enumerate(me.materials)])
from collections import Counter
cnt=Counter(p.material_index for p in me.polygons)
print("各材质槽面数:", dict(cnt))
for i,m in enumerate(me.materials):
    if m:
        print(f"  槽{i} {m.name}: diffuse={tuple(round(c,3) for c in m.diffuse_color)}")
# 自定义属性/顶点组
print("属性:", [a.name for a in me.attributes][:12])
print("顶点组:", [g.name for g in head.vertex_groups][:8])
