# Blender 5.x Slotted Action 系统（行走动画/外部动画驱动外部骨架）

2026-08-25/26 实测。5.1 起 Action 改为分层结构，旧 `action.fcurves` 不存在。

## 数据结构
```
action.layers[] → .strips[] (type='KEYFRAME') → .channelbags[] → .fcurves[]
```

## 驱动外部骨架的必要条件（缺一不可）
1. `obj.animation_data.action = action`
2. **`obj.animation_data.action_slot` 必须指向该 action 自己的 slot**
   - 复制 action 后，`new_action.slots` 与旧 action 的 slot 是不同对象；`new_action.slots.new(id_type='OBJECT', name=...)` 创建
   - RuntimeError "slot does not belong to the assigned Action" = 把旧 action 的 slot 赋给了新 action
   - 更可靠：不复制 action，直接复用原 action 的 `slots[0]`（骨骼名一致即可按名匹配 pose channel）
3. 骨骼名必须含 `mixamorig:` 前缀——Mixamo FBX 的 F 曲线 data_path 是 `pose.bones["mixamorig:Hips"]`

## API 陷阱（5.1 实测）
- `ActionSlot` 没有 `.name` 属性（用 `.identifier` / `.handle`）
- `slot in act.slots` 报 TypeError——collection 不支持 `in`，用 identifier 列表比较
- `slots.new()` 只收 2 个参数（id_type, name），没有 target 参数

## Mixamo 行走动画原地播放
Hips 的 location F 曲线是全局根动作位移，直接套用会让模型飞走。原地循环：删除 channelbag 里 `Hips`+`location` 的 F 曲线（只留旋转）。

## 验证驱动是否生效
不要只看 action 绑上了——实测 pose bone 矩阵跨帧变化：`frame_set(1)` vs `frame_set(20)` 对比 `pb.matrix`。
注意：background `-b` 模式下曾出现"骨骼矩阵动了但网格变形 0"的求值不一致，GUI 里再核一遍。
