import bpy
from mathutils import Vector
# 对比: 用户thigh点 vs 当前骨骼胯点 vs 腿mesh中心 vs 建议股骨头位置
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\03_骨骼绑定.blend")
arm = bpy.data.objects.get('MixamoSkeleton')
body = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
bm = body.matrix_world

# 用户标记点
MK = {}
with bpy.data.libraries.load(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\01_AI打点.blend") as (src, dst):
    dst.objects = [n for n in src.objects if n.endswith('_loc') or n.endswith('_loc_sym')]
_linked = []
for o in dst.objects:
    bpy.context.scene.collection.objects.link(o); _linked.append(o)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for o in _linked: MK[o.name] = o.evaluated_get(dg).matrix_world.translation.copy()
for o in _linked: bpy.data.objects.remove(o, do_unlink=True)

thigh = MK['thigh_loc']
print(f"用户thigh点: ({thigh.x:.3f},{thigh.y:.3f},{thigh.z:.3f})")
up = arm.data.bones['LeftUpLeg']
print(f"当前胯骨head: ({up.head_local.x:.3f},{up.head_local.y:.3f},{up.head_local.z:.3f})")

# 胯高度腿mesh的x范围(找内外侧边界)
hip_z = up.head_local.z
xs = []
for v in body.data.vertices:
    w = bm @ v.co
    if abs(w.z - hip_z) < 0.03 and w.x > 0.02:
        xs.append(w.x)
if xs:
    inner, outer = min(xs), max(xs)
    center = (inner+outer)/2
    print(f"\n胯高{hip_z:.2f}处左腿mesh: 内侧x={inner:.3f} 外侧x={outer:.3f} 中心x={center:.3f} 腿宽{(outer-inner)*100:.1f}cm")
    # 股骨头解剖位置: 距外侧约1/3腿宽处(偏内)
    femur_head = outer - (outer-inner)*0.35
    print(f"建议股骨头位置(x): {femur_head:.3f} (外侧内收35%腿宽)")
    print(f"对比: 用户thigh.x={thigh.x:.3f} 当前骨骼.x={up.head_local.x:.3f} mesh中心={center:.3f}")
