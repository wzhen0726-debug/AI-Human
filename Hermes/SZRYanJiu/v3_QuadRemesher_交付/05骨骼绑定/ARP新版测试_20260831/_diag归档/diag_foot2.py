import bpy
from mathutils import Vector
arm = bpy.data.objects.get('MixamoSkeleton')
mw = arm.matrix_world
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
bev = body.evaluated_get(dg)
scn = bpy.context.scene

# 全身mesh最低点(不过滤顶点组, 看绝对最低) + 脚底区(z<0.2且在脚x范围的点)
print("帧 | 全身mesh最低z | 左脚底最低z | 右脚底最低z | L踝z | R踝z")
lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}
for f in range(scn.frame_start, scn.frame_end + 1):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    lfa = (mw @ arm.pose.bones['mixamorig:LeftFoot'].head).z
    rfa = (mw @ arm.pose.bones['mixamorig:RightFoot'].head).z
    vs = bev.data.vertices
    allmin = min(v.co.z for v in vs)
    lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
    rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
    tag = "  ← 双脚腾空!" if min(lmin, rmin) > 0.03 else ""
    print(f"{f:3d} | {allmin:.3f} | L{lmin:.3f} R{rmin:.3f} | L{lfa:.3f} R{rfa:.3f}{tag}")
