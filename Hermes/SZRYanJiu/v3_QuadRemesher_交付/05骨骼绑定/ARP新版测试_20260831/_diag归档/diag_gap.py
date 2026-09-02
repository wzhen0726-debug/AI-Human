import bpy
from mathutils import Vector
# 计算每帧"支撑脚(较低那只)脚底间隙", 生成Hips垂直补偿让支撑脚贴地
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
scn = bpy.context.scene
mw = arm.matrix_world

lf_i = {g.index for g in body.vertex_groups if 'LeftFoot' in g.name or 'LeftToe' in g.name}
rf_i = {g.index for g in body.vertex_groups if 'RightFoot' in g.name or 'RightToe' in g.name}

print("帧 | 左脚底 | 右脚底 | 支撑脚间隙(拟下沉量)")
gaps = {}
for f in range(scn.frame_start, scn.frame_end + 1):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    bev = body.evaluated_get(dg)
    vs = bev.data.vertices
    lmin = min((v.co.z for v in vs if any(g.group in lf_i and g.weight>0.1 for g in v.groups)), default=9)
    rmin = min((v.co.z for v in vs if any(g.group in rf_i and g.weight>0.1 for g in v.groups)), default=9)
    gap = min(lmin, rmin)  # 支撑脚(较低者)离地面高度
    gaps[f] = gap
    if f % 4 == 1 or f < 4:
        print(f"{f:3d} | L{lmin:.3f} | R{rmin:.3f} | 下沉{gap:.3f}")
avg_gap = sum(gaps.values())/len(gaps)
print(f"\n平均支撑脚间隙: {avg_gap:.4f}m = {avg_gap*100:.1f}cm")
print(f"最大间隙: {max(gaps.values()):.3f}, 最小: {min(gaps.values()):.3f}")
