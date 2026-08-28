# Mixamo动画重定向到自定义骨骼 (Blender 5.1, 已验证)

> 验证场景: Standard Walk.fbx 应用到自写54骨骼rig, 5454/143708顶点变形, 最大位移22.4cm, 原地循环。

## 前置: 骨骼名必须带 mixamorig: 前缀
F曲线data_path是 `pose.bones["mixamorig:Hips"]`, 骨骼名必须完全一致(含前缀)。给骨骼改名时Blender会自动联动重命名顶点组。

## Blender 5.1 Slotted Action 新API(与旧版完全不同)
- `action.fcurves` 是空的(0条) — F曲线在 `action.layers[i].strips[j].channelbag(slot).fcurves`
- `ActionSlot` **没有 .name 属性**, 用 `.identifier` / `.handle`
- `action.slots.new(id_type='OBJECT', name)` 只有2个参数
- **绑定关键**: 必须 `rig.animation_data.action = act` 且 `rig.animation_data.action_slot = act.slots[0]` — **复用原slot**, 新建的空slot没有channelbag(F曲线), 动画不会求值

## 步骤(后台可跑)
1. `bpy.ops.import_scene.fbx(filepath=WALK_FBX, use_anim=True, automatic_bone_orientation=False)`
2. `new_act = walk_arm.animation_data.action.copy()`; 删除Hips的location F曲线(3条) → 原地循环(否则模型随根动作位移飞走, 实测位移4.66m)
3. 绑定到目标rig(复用slot0, 见上)
4. 测试前**剥掉变形骨上的约束** — ARP生成的rig在变形骨上留COPY_LOCATION/STRETCH_TO(实测77个), 症状是"F曲线数值在变但姿态矩阵不动"

## 验证方法
比较两帧的 `pose.bones['mixamorig:LeftUpLeg'].matrix` 四元数; 网格变形用evaluated depsgraph顶点位置差分。相关脚本: `05骨骼绑定/B_骨骼绑定/walk_test_fix.py`, `C_诊断工具/diag_walk_action_struct3.py`