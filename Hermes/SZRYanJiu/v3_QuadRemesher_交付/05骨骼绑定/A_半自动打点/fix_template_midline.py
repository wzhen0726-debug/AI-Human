"""修复打点模板两大错误 (根因修复, 2026-08-25):
错误1: 颈根/会阴偏离中线 (颈根x=-0.037, 会阴x=+0.021)
  根因: Shrinkwrap NEAREST_SURFACE 沿模型真实(不对称)表面投影, 把中线点带偏
  修复: 在中线标记点约束栈里, Shrinkwrap 之后追加 LIMIT_LOCATION 钳制 X=0
        Blender 约束按栈顺序求值: 先吸附表面→再钳制X, 点贴表面且严格在中线
错误2: 文字牌平躺朝上, 正面视图看是一条线
  修复: rotation_euler=(+pi/2,0,0) → 法线朝−Y(正视镜头方向), 正面直接可读
"""
import bpy, math
from mathutils import Vector

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

coll_m = bpy.data.collections.get("LM_M")

# --- 修复1: 中线点约束栈追加 LIMIT_LOCATION 锁X=0 ---
locked = 0
for o in sorted([x for x in coll_m.objects], key=lambda x: x.name):
    # 清掉旧的X锁定约束(可重复运行)
    for c in list(o.constraints):
        if c.name.startswith("X锁定"):
            o.constraints.remove(c)
    # 确保有Shrinkwrap在前
    has_sw = any(c.type == 'SHRINKWRAP' for c in o.constraints)
    if not has_sw:
        body = None
        for ob in bpy.data.objects:
            if ob.type == 'MESH' and 'eye' not in ob.name.lower() and len(ob.data.vertices) > 1000:
                body = ob
                break
        if body:
            sw = o.constraints.new('SHRINKWRAP')
            sw.target = body
            sw.shrinkwrap_type = 'NEAREST_SURFACE'
            sw.distance = 0.0
    # 追加X锁定(栈顶, 最后生效)
    c = o.constraints.new('LIMIT_LOCATION')
    c.name = "X锁定_保证在中线"
    c.use_min_x = True
    c.use_max_x = True
    c.min_x = 0.0
    c.max_x = 0.0
    c.owner_space = 'WORLD'
    locked += 1
    print(f"  X锁定: {o.name} (约束栈={[x.type for x in o.constraints]})")

# --- 修复2: 文字牌竖起来朝前 ---
# 正视相机在−Y看向+Y(模型正面朝−Y), 文字法线须朝−Y才正面可读 → 绕X转+90°(+Z→−Y)
# (教训: -90°会镜像, 因为看到的是文字背面; 已用渲染图实测验证)
for o in bpy.data.objects:
    if o.type == 'FONT' and o.name.startswith("打点操作提示"):
        o.rotation_euler = (math.pi / 2, 0.0, 0.0)
        print(f"  文字牌朝向修正: {o.name} rot_x=+90°(法线朝−Y,正视可读)")

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"FIX_TEMPLATE_DONE 中线锁定={locked}")
