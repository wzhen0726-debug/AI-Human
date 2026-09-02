import bpy
from mathutils import Vector
# 计算小腿mesh在膝关节高度的几何中心(x,y), 对比当前小腿骨位置
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
mw = arm.matrix_world
bm = body.matrix_world

# 取小腿中段高度(膝和踝之间), 找该高度附近左腿的mesh顶点, 算x,y中心
leg_b = arm.data.bones['LeftLeg']
knee_z = (mw @ leg_b.head_local).z
ankle_z = (mw @ leg_b.tail_local).z
mid_z = (knee_z + ankle_z) / 2
print(f"小腿: 膝z={knee_z:.3f} 踝z={ankle_z:.3f} 中段z={mid_z:.3f}")
print(f"当前小腿骨head=({leg_b.head_local.x:.3f},{leg_b.head_local.y:.3f}) (膝处)")

# 左腿(+X侧), 该高度±2cm范围内的顶点
pts = []
for v in body.data.vertices:
    w = bm @ v.co
    if abs(w.z - mid_z) < 0.02 and w.x > 0.03:  # 左腿
        pts.append((w.x, w.y))
if pts:
    cx = sum(p[0] for p in pts)/len(pts)
    cy = sum(p[1] for p in pts)/len(pts)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    print(f"小腿中段mesh中心: x={cx:.3f} y={cy:.3f} (x范围{min(xs):.3f}~{max(xs):.3f}, y范围{min(ys):.3f}~{max(ys):.3f}, {len(pts)}点)")
    print(f"骨骼偏移: dx={leg_b.head_local.x-cx:+.3f} dy={leg_b.head_local.y-cy:+.3f}")
