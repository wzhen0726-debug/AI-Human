# 半自动打点模板修正记录 (2026-08-25, 覆盖旧判断)

本文件**修正** `rigging-marker-template.md` 中的一处过期判断。两处冲突时以本文件为准。

## ❌ 旧判断（已推翻）

> "关键坑：关节在肢体内部 → 不能加Shrinkwrap"

这是我早期的错误推断。实际后果：标记点悬浮不贴皮肤，用户根本无法拖动定位，
判定模板"完全不对"、"你这对应了啥？？"。

## ✅ 正确做法（用户验证）

**所有标记点（含关节点）都加 `SHRINKWRAP` 吸附**，与 01A 眼窝模板完全一致：

```python
sw = e.constraints.new(type='SHRINKWRAP')
sw.target = body_mesh          # 身体网格对象
sw.shrinkwrap_type = 'NEAREST_SURFACE'
sw.distance = 0.0
```

- 生成脚本（rig_semiauto_setup.py）：R侧+中线全部8点都加
- **镜像脚本（mirror_rig_markers.py）：L侧镜像出的点也要加**
  （照 01A mirror_markers.py 第33-36行，容易漏）
- 吸附让球拖着走时贴皮肤，是"半自动打点可用"的核心体验

## 模板"打开即可用"验收清单（用户逐项检查过）

| 项 | 要求 | 后台(-b)可实现? |
|---|---|---|
| 视角 | 正视全身（不是头顶） | ✅ 可存 |
| 视野 | 3m，全身1.80m完整可见 | ✅ 可存 |
| 着色 | 材质预览 MATERIAL | ✅ 可存 |
| 投影 | 正交 | ✅ 可存 |
| 默认工具 | 移动工具 | ❌ -b下崩溃，改用中文文字牌提示"按G" |
| 操作提示 | 场景内中文文字牌（雅黑字体） | ✅ |
| 吸附 | 8/8标记点有Shrinkwrap | ✅ |

## 后台视口设置的可持久化范围（2026-08-25实测）

- ✅ `bpy.data.workspaces` → screen → VIEW_3D area → space 上设
  `shading.type` / `region_3d.view_location/view_distance/view_rotation/view_perspective`，
  对**每个工作区**都设，然后 `save_as_mainfile()` → 重开读回验证，全部持久化。
  （此前"后台存不进视口"的记忆过宽——存不进的是工具状态和布局拆分。）
- ❌ `bpy.ops.wm.tool_set_by_id` 在 -b 下 EXCEPTION_ACCESS_VIOLATION（C级崩溃，catch不住）
- ❌ `workspace.active_tool_id_name` 在 Blender 5.1 不存在；`workspace.tools` 后台为空
- → 工具问题的替代方案：场景内中文文字牌写明"按G切换移动工具"
- 双视口拆分只能在带GUI的会话里做

## 交付纪律（用户两次纠正）

1. 用户说"参考01A的模板"= 把参考脚本**逐项**列出并逐条落实，不是挑几条
2. 生成后必须**打开保存的blend读回**验证每项特性真实存在
3. 文件日期更新 ≠ 内容正确；用户检查内容，不是日期
4. 汇报"参考了什么"时要给出具体行号/字段对照，不接受"参考的足够"这种含糊说法
