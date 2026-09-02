import bpy, json
from mathutils import Vector
arm = bpy.data.objects.get('MixamoSkeleton')
spec = json.load(open(r'E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/v3_QuadRemesher_交付/05骨骼绑定/_工作区_过程文件/logs/mixamo_rest_spec.json', encoding='utf-8'))['bones']
for n in ['mixamorig:LeftShoulder','mixamorig:LeftArm','mixamorig:Hips']:
    b = spec.get(n)
    if b:
        print(f"SPEC {n}: keys={list(b.keys())} head={b.get('head')}")
print()
mw = arm.matrix_world
bpy.context.scene.frame_set(18); bpy.context.view_layer.update()
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
bev = body.evaluated_get(dg)
h = mw @ arm.pose.bones['mixamorig:LeftHand'].head
print("帧18 LeftHand骨:", [round(v,3) for v in h])
lh_idx = {g.index for g in body.vertex_groups if 'LeftHand' in g.name}
pts = [v.co.copy() for v in bev.data.vertices if any(g.group in lh_idx and g.weight>0.5 for g in v.groups)]
if pts:
    c = sum(pts, Vector()) / len(pts)
    print("帧18 mesh手部质心:", [round(v,3) for v in c], f"({len(pts)}顶点)")
# 同样看膝
k = mw @ arm.pose.bones['mixamorig:LeftLeg'].head
print("帧18 LeftLeg骨(膝):", [round(v,3) for v in k])
kn_idx = {g.index for g in body.vertex_groups if g.name=='mixamorig:LeftLeg'}
pts2 = [v.co.copy() for v in bev.data.vertices if any(g.group in kn_idx and g.weight>0.5 for g in v.groups)]
if pts2:
    c2 = sum(pts2, Vector()) / len(pts2)
    print("帧18 mesh小腿质心:", [round(v,3) for v in c2], f"({len(pts2)}顶点)")
