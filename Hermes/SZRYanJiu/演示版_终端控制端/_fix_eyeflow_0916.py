# -*- coding: utf-8 -*-
"""2026-09-16 用户要求: 眼球在02输出中出现, 且UV/烘焙/绑定/导出全程连贯
改动: ① 02碗脚本: 把眼球对象并入输出文件
     ② 04烘焙: 物体选取改稳健(取最大网格), FBX导出含眼球
     ③ 05绑定: 眼球已在新网格中则不重复并入(防重复), 蒙皮组防重复
"""
import ast

D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端/"

# ===== ① 02碗脚本: 眼球并入输出 =====
p = D + "交付/02QuadRemesher拓扑/scripts/02qr_socket_cup.py"
s = open(p, encoding="utf-8").read()
old = '''bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)'''
new = '''# ---- v19(用户: 眼球要在02输出中出现, 后续UV/烘焙/绑定/导出全程连贯) ----
# 把01_2里的眼球对象(Eye002_L/R)并入本文件(保持世界位置; 只并入眼球, 不带高模)
try:
    _existing = [o for o in bpy.data.objects if o.name.startswith('Eye002')]
    if not _existing:
        with bpy.data.libraries.load(EYE_BLEND) as (_src, _dst):
            _dst.objects = [n for n in _src.objects if n.startswith('Eye002')]
        _eyes = [o for o in _dst.objects if o is not None]
        for _o in _eyes:
            bpy.context.scene.collection.objects.link(_o)
        print(f"眼球并入: {[o.name for o in _eyes]}")
    else:
        print(f"眼球已存在, 跳过: {[o.name for o in _existing]}")
except Exception as _e:
    print(f"眼球并入失败: {_e}")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)'''
assert old in s, "cup保存行未匹配"
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s); ast.parse(s); print("① 02碗脚本 OK")

# ===== ② 04烘焙: 选取稳健 + FBX含眼球 =====
p = D + "交付/04纹理烘焙/scripts/04_bake.py"
s = open(p, encoding="utf-8").read()
old = "low_poly = [o for o in bpy.data.objects if o.type == 'MESH'][0]"
new = ("# 2026-09-16: 文件里现在含眼球(02起全程连贯), 不能取[0]; 低模=最大网格\n"
       "low_poly = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))")
assert old in s, "04低模选取未匹配"; s = s.replace(old, new, 1)
old = """with bpy.data.libraries.load(HIGH_POLY) as (data_from, data_to):
    data_to.objects = data_from.objects
for obj in data_to.objects:
    bpy.context.collection.objects.link(obj)
high_poly = [o for o in bpy.data.objects if o.type == 'MESH' and o != low_poly][0]"""
new = """with bpy.data.libraries.load(HIGH_POLY) as (data_from, data_to):
    data_to.objects = data_from.objects
_loaded = []
for obj in data_to.objects:
    if obj is not None and obj.type == 'MESH':
        bpy.context.collection.objects.link(obj)
        _loaded.append(obj)
# 2026-09-16: 从"新载入的"里取最大=高模(避免多物体时选错)
high_poly = max(_loaded, key=lambda o: len(o.data.vertices))"""
assert old in s, "04高模选取未匹配"; s = s.replace(old, new, 1)
old = """bpy.ops.object.select_all(action='DESELECT')
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
bpy.ops.export_scene.fbx("""
new = """# 2026-09-16: 导出含眼球(全场景剩余网格: 低模+眼球; 高模已删)
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.select_set(True)
bpy.context.view_layer.objects.active = low_poly
bpy.ops.export_scene.fbx("""
assert old in s, "04导出选取未匹配"; s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s); ast.parse(s); print("② 04烘焙 OK")

# ===== ③ 05绑定: 防重复并入 =====
p = D + "交付/05骨骼绑定/ARP新版测试_20260831/scripts/step3_to_7_rig_and_walk.py"
s = open(p, encoding="utf-8").read()
old = '''EYE_BLEND = os.path.join(BASE, "..", "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
EYE_BLEND = os.path.normpath(EYE_BLEND)
head_head = None  # Head骨世界位置
mw_arm = arm.matrix_world
head_bone = arm.data.bones.get('Head')
if head_bone and os.path.exists(EYE_BLEND):
    # link眼球对象(保持其世界位置)
    with bpy.data.libraries.load(EYE_BLEND) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith('Eye002')]
    eyes = [o for o in dst.objects if o is not None]
    for o in eyes:
        bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()'''
new = '''EYE_BLEND = os.path.join(BASE, "..", "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
EYE_BLEND = os.path.normpath(EYE_BLEND)
head_head = None  # Head骨世界位置
mw_arm = arm.matrix_world
head_bone = arm.data.bones.get('Head')
# 2026-09-16 用户要求: 眼球从02起全程连贯(02输出→03UV→04烘焙都含眼球) → 此处不再重复并入
_eye_existing = [o for o in bpy.data.objects if o.name.startswith('Eye002')]
if head_bone and _eye_existing:
    eyes = _eye_existing
    bpy.context.view_layer.update()
    print(f"眼球已随网格传来(02起连贯), 直接蒙皮: {[o.name for o in eyes]}")
elif head_bone and os.path.exists(EYE_BLEND):
    # 兼容: 旧流程/网格里没有眼球时, 从01_2 link并入(保持其世界位置)
    with bpy.data.libraries.load(EYE_BLEND) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith('Eye002')]
    eyes = [o for o in dst.objects if o is not None]
    for o in eyes:
        bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()'''
assert old in s, "05并入段未匹配"; s = s.replace(old, new, 1)
old = """        vg = o.vertex_groups.new(name='mixamorig:Head')
        vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')"""
new = """        vg = o.vertex_groups.get('mixamorig:Head') or o.vertex_groups.new(name='mixamorig:Head')
        vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')"""
assert old in s, "05顶点组未匹配"; s = s.replace(old, new, 1)
old = "# 眼球是独立物体不进QR/烘焙, 在绑定阶段并入(01A设计: 只在05绑定/06导出时并入)。\n# 从01A眼球摆入产物link入 Eye002_L/R, 骨骼绑到Head(眼球跟头动)。"
new = "# 2026-09-16 用户要求: 眼球从02起全程连贯(02输出/03UV/04烘焙/导出都含眼球)。\n# 本步骤: 若网格里已带眼球则直接蒙皮Head骨; 若没有(旧文件)才从01_2并入。"
assert old in s, "05注释未匹配"; s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s); ast.parse(s); print("③ 05绑定 OK")
print("ALL_PATCHED")
