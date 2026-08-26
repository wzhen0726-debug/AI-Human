"""修复: 关节标记点去掉Shrinkwrap吸附 (2026-08-25根因修复)
根因: 肩/肘/腕/膝/踝是关节中心(肢体内部解剖点), Shrinkwrap NEAREST_SURFACE
会主动阻止用户把点放到皮肤内部, 导致骨旋转轴心偏到皮肤表面(如肩点打到三角肌前束表面)
→ 蒙皮变形异常. 01A眼睑点吸附正确是因为那是表面特征, 关节点不同.
修复: 5个关节点烘焙当前求值位置→删除吸附约束(保留用户已拖的位置);
      中线3点保留吸附+X锁(它们是表面标志); 更新文字牌说明.
"""
import bpy, math

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

JOINT_KEYS = ("shoulder", "elbow", "wrist", "knee", "ankle")

depsgraph = bpy.context.evaluated_depsgraph_get()

removed = 0
for o in bpy.data.objects:
    if not o.name.startswith("LM_"):
        continue
    is_joint = any(k in o.name for k in JOINT_KEYS)
    if not is_joint:
        continue
    # 1. 烘焙当前求值位置(保留用户已拖到的位置, 防止删约束后弹回初始坐标)
    eval_obj = o.evaluated_get(depsgraph)
    baked = eval_obj.matrix_world.translation.copy()
    # 2. 删除吸附约束
    for c in list(o.constraints):
        if c.type == 'SHRINKWRAP':
            o.constraints.remove(c)
            removed += 1
    # 3. 写回烘焙位置
    o.location = baked
    print(f"  {o.name}: 去吸附, 位置保留 ({baked[0]:.3f}, {baked[1]:.3f}, {baked[2]:.3f})")

print(f"共移除 {removed} 个吸附约束 (5个关节点)")

# 中线点确认仍有吸附+X锁
for o in bpy.data.objects:
    if o.name.startswith("LM_") and any(k in o.name for k in ("headtop", "neckbase", "crotch")):
        types = [c.type for c in o.constraints]
        print(f"  中线 {o.name}: 约束保留 {types}")

# 更新文字牌说明
for o in bpy.data.objects:
    if o.type == 'FONT' and o.name.startswith("打点操作提示"):
        o.data.body = (
            "打点操作提示：\n"
            "1. 按 G 切换移动工具，拖动彩色球到关节位置。\n"
            "2. 黄点(头顶/颈根/会阴)贴皮肤吸附，在中线上。\n"
            "3. 红点(肩肘腕膝踝)无吸附：放到关节中心(肢体内部)。\n"
            "   肩=肩峰下2cm手臂厚度中间 肘=肘弯中间 膝=膝盖骨中间偏下。\n"
            "   用小键盘1(正面)/3(侧面)配合调整深度。\n"
            "4. 只调右侧8个点，左侧自动镜像。Ctrl+S 保存。"
        )
        print("  文字牌已更新")

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("已保存")
print("FIX_JOINT_SNAP_DONE")
