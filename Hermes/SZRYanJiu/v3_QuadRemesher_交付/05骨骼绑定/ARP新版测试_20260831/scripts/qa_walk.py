"""04行走测试 腿部质量自检 — 膝盖朝向/划圆/滑步/起伏"""
import bpy
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\04_行走测试.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get()
scn = bpy.context.scene
mw = arm.matrix_world

def pb(n):
    return arm.evaluated_get(dg).pose.bones.get('mixamorig:'+n)

print("帧 | 膝外偏(°) | 脚底贴地z | Hips_z | 步态")
# 膝外偏: 小腿骨方向的世界x分量(理想行走应≈0, 纯前后)
for f in range(scn.frame_start, scn.frame_end+1, 4):
    scn.frame_set(f); bpy.context.view_layer.update()
    # 右小腿方向
    lg = pb('RightLeg')
    d = (mw @ lg.tail) - (mw @ lg.head)
    dn = d.normalized()
    # 膝外偏角: 骨骼方向在xz平面偏离垂直的角度... 改为测膝盖横向摆动
    # 用膝盖head的x位置相对静止的偏移
    knee_x = (mw @ lg.head).x
    # 脚底最低
    vs = body.evaluated_get(dg).data.vertices
    sole = min(v.co.z for v in vs)
    hips_z = (mw @ pb('Hips').head).z
    print(f"{f:3d} | 小腿dir=({dn.x:.2f},{dn.y:.2f},{dn.z:.2f}) 膝x={knee_x:.3f} | 脚底{sole:.3f} | Hips{hips_z:.3f}")

# 起伏检测: Hips z 变化幅度
print("\nHips垂直起伏检测:")
hs = []
for f in range(scn.frame_start, scn.frame_end+1):
    scn.frame_set(f); bpy.context.view_layer.update()
    hs.append((mw @ pb('Hips').head).z)
print(f"  Hips z范围: {min(hs):.3f} ~ {max(hs):.3f}, 起伏{(max(hs)-min(hs))*100:.1f}cm")
print(f"  (静止0.876, 正常行走起伏2-5cm; 0=完全无起伏会滑步僵硬)")
