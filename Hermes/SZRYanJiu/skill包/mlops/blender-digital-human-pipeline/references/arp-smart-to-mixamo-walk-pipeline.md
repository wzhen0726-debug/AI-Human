# ARP Smart 后台绑定 → Mixamo 对齐 → 行走动画 (2026-08-25 全流程打通)

> 本次会话完整打通：ARP 后台自动绑定 → Mixamo 65 骨骼命名 → 行走动画测试通过。
> 模型身高 1.80m（与 ARP 模板匹配，无需缩放），这是关键前提。

## ARP 后台绑定的 4 个必要补丁（缺一不可）

1. **popup 崩溃补丁**: `display_popup_message` → print，否则后台 `popup_menu` 崩溃
2. **截图补丁**: `_screenshot_char` 用 OpenGL，后台失败。**必须用 Emission 自发光材质**（0.8 灰 + 0.04 暗背景）——后台无灯光，BSDF 渲染成黑色剪影，AI 识别不出人体（关键点全在图像边缘）
3. **截图文件名**: 推理 exe 固定读 `front1.jpg`/`char_side.jpg`/`char_top.jpg`，必须存 `.jpg`（`image_settings.file_format='JPEG'`），存 `.png` 会找不到文件
4. **`arp_smart_AI_body_samples=1`**: 默认 2 张正面样本会找 `front2.jpg` 报错

## AI 路径配置（重要坑）
`ai_presets_path` 设到 `...\AutoRigPro\AI`（**不以 inference 结尾**）——ARP 自动追加 `inference\`，否则路径变成 `\AI\inference\inference\front1_kp.py`

## 关键坑 1：`guess_markers` 臂角崩溃
`_set_markers_from_keypoints` 算 `arm_angle=(shoulder_loc-hand_loc).angle(...)`，
若 shoulder==hand（零向量）抛 `ValueError: zero length vectors`。
**解决**: try/except 包裹，几何修正函数覆盖标记位置后继续 `go_detect`。

## 关键坑 2：`parent_set` 后台 poll 失败
`bpy.ops.object.select_all/parent_set` 在后台模式 poll 失败。
**解决**: 用纯 Python `o.select_set()` + `temp_override(window,screen,area,region)` 包裹 `parent_set`。
**成功结果**: 339 骨骼 + 67 顶点组 + 100% 权重。

## 关键坑 3：ARP 变形骨骼名不是 Mixamo
ARP 生成 `root.x`/`spine_01.x`/`arm_stretch.l` 等。需 `arp_to_mixamo.py`：
1. 合并 twist/stretch 骨骼权重到主骨骼
2. 重命名 59 根变形骨 + 顶点组为 Mixamo 名
3. 删除 280 根非变形骨骼（控制器/IK 极）
4. `fill_mixamo_ends.py` 补齐 6 根缺失骨（Spine + HeadTop/Thumb4/Toe 末端）
5. `add_mixamo_prefix.py` 加 `mixamorig:` 前缀（动画 F 曲线用此前缀）

## 关键坑 4：Blender 5.x Slotted Action（最重要！）
**根因**: 复制 action 后骨骼不动。Blender 5.x 新动画层系统：
- `action.fcurves` 不存在，F 曲线在 `action.layers[0].strips[0].channelbag(slot).fcurves`
- 光设 `animation_data.action` 不够，**必须设 `animation_data.action_slot`**
- **正确做法**: 直接复用行走动画的**原始 slot**（F 曲线所在的 slot），不要新建空 slot
  ```python
  rig_arm.animation_data.action = rig_action
  rig_arm.animation_data.action_slot = walk_arm.animation_data.action_slot  # 复用原slot
  ```

## 关键坑 5：ARP 控制器约束锁死变形骨（动画飞/不动的根源）
ARP 生成的骨架含 FK/IK 控制器约束。改名后变形骨仍被 `COPY_LOCATION/COPY_ROTATION/STRETCH_TO` 锁死。
**症状**: 动画四元数在变，但姿态不动（或先飞掉）。
**解决**: 删除所有变形骨的 `pb.constraints`（本次清 77 个）。

## 关键坑 6：行走动画"飞走"（根动作）
Mixamo 动画的 `mixamorig:Hips` location 是**全局坐标**（走路位移）。
**解决**: 原地走路 → 删除 Hips 的 location F 曲线（保留 rotation）：
```python
for fc in list(cb.fcurves):
    if 'mixamorig:Hips' in fc.data_path and 'location' in fc.data_path:
        cb.fcurves.remove(fc)
```

## 最终验证标准（用户提供的验收）
导入 `原始模型/Mixamo动画文件/Standard Walk.fbx`：
- 骨骼名 65/65 匹配 ✓
- 四肢旋转 >0°（左腿 40°、大腿 22°、手臂 6°）✓
- 网格变形但最大位移 <1m（无飞走）✓
