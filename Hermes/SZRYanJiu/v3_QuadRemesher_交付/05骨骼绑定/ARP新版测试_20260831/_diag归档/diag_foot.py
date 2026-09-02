import bpy
from mathutils import Vector
arm = bpy.data.objects.get('MixamoSkeleton')
mw = arm.matrix_world
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
bev = body.evaluated_get(dg)

# mesh脚底最低点(脚+脚趾顶点组)
foot_idx = {g.index for g in body.vertex_groups if 'Foot' in g.name or 'Toe' in g.name}
print("帧 | 踝骨z | 脚底mesh最低z | 全身mesh最低z")
for f in [1, 6, 12, 18, 24, 30]:
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    lfa = (mw @ arm.pose.bones['mixamorig:LeftFoot'].head).z
    rfa = (mw @ arm.pose.bones['mixamorig:RightFoot'].head).z
    soles = [v.co.z for v in bev.data.vertices if any(g.group in foot_idx and g.weight>0.3 for g in v.groups)]
    allmin = min(v.co.z for v in bev.data.vertices)
    print(f"{f:3d} | L踝{lfa:.3f} R踝{rfa:.3f} | 脚底最低{min(soles):.3f} | 全身最低{allmin:.3f}")

# 静止帧脚的位置
bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
print("\n静止 LeftFoot骨: head_z=%.3f tail_z=%.3f" % ((mw@arm.data.bones['mixamorig:LeftFoot'].head_local).z, (mw@arm.data.bones['mixamorig:LeftFoot'].tail_local).z))
print("静止 LeftToeBase tail_z=%.3f" % (mw@arm.data.bones['mixamorig:LeftToeBase'].tail_local).z)
