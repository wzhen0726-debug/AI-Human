import bpy
from mathutils import Vector
# 检查腿骨是否在大腿mesh中心(不是偏到表面)
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
mw = arm.matrix_world
bvh = __import__('mathutils.bvhtree', fromlist=['BVHTree']).BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())

# 对大腿/小腿若干采样点, 找到最近的mesh表面点, 看骨骼是否在体内(距离>0即在体内)
print("腿骨在mesh内的深度检测(正=在体内):")
for bn in ['LeftUpLeg','LeftLeg','RightUpLeg','RightLeg']:
    b = arm.data.bones[bn]
    for t in [0.3, 0.5, 0.7]:  # 沿骨骼采样
        p = mw @ (b.head_local.lerp(b.tail_local, t))
        # 从该点向外射多个方向找最近表面, 判断在体内外
        loc, norm, idx, dist = bvh.find_nearest(p)
        # 用射线向内测: 从骨点向身体中线(-x方向)发射
        hit, hn, hi, hd = bvh.ray_cast(p, Vector((-1 if p.x>0 else 1, 0, 0)))
        print(f"  {bn}@{t}: pos=({p.x:.3f},{p.y:.3f},{p.z:.3f}) 最近表面距{dist*100:.1f}cm")
