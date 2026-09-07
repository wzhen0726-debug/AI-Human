"""验证: 把Hips.tail连到双腿中间连接点 + use_connect后, 动画是否仍正常
方案: Hips.tail ← (LeftUpLeg.head + RightUpLeg.head)/2, 然后Hips→UpLeg use_connect=True
对比: 改动前后行走动画的脚部世界位置(应几乎不变)"""
import bpy, os
from mathutils import Vector

DEMO = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831"
P = os.path.join(DEMO, "04_动作测试.blend")
bpy.ops.wm.open_mainfile(filepath=P)
arm = bpy.data.objects['MixamoSkeleton']
arm.animation_data.action = bpy.data.actions['Standard Walk']
scn = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

def foot_z(f):
    scn.frame_set(f); bpy.context.view_layer.update()
    return (arm.evaluated_get(dg).pose.bones['mixamorig:LeftFoot'].matrix.translation.z)

# 改动前脚部轨迹
before = [foot_z(f) for f in [1, 9, 18, 27, 36]]
print("改动前 LeftFoot.z:", [round(x,4) for x in before])

# 编辑模式改Hips.tail + use_connect
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
hips = eb['mixamorig:Hips']
lul = eb['mixamorig:LeftUpLeg']
rul = eb['mixamorig:RightUpLeg']
mid = (lul.head + rul.head) / 2
print(f"Hips.tail: {tuple(round(x,3) for x in hips.tail)} → {tuple(round(x,3) for x in mid)}")
hips.tail = mid
lul.use_connect = True
rul.use_connect = True
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

# 改动后脚部轨迹(动画action没动, 关键帧里的旋转应自动适应新rest)
after = [foot_z(f) for f in [1, 9, 18, 27, 36]]
print("改动后 LeftFoot.z:", [round(x,4) for x in after])
diff = max(abs(a-b) for a, b in zip(before, after))
print(f"脚部世界z最大偏差: {diff*1000:.2f}mm")

# 检查Hips→UpLeg现在是否视觉连接
lul_w = arm.data.bones['mixamorig:LeftUpLeg']
hips_w = arm.data.bones['mixamorig:Hips']
gap = (hips_w.tail_local - lul_w.head_local).length * 1000
print(f"改动后 Hips.tail 到 LeftUpLeg.head: {gap:.2f}mm, use_connect={lul_w.use_connect}")
print("TEST_DONE")
