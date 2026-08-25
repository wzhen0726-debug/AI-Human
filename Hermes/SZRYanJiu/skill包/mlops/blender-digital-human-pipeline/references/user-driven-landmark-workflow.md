# 16-Point Body Landmark Workflow

## 概述

当自动特征点检测失败时（A-pose比例估算误差30-50cm、拓扑分析不对称dX>0.2），用户提供Blender空对象手动标记工作流。

## 用户原话

"不能在bl让我使用空对象给你打点嘛？你给我提供好要改好名字的的空对象，然后告诉我要放的位置"

## 工作流程

### Step 1: 创建空对象场景

```python
import bpy, os
from mathutils import Vector

# 16个特征点（名称和初始位置）
landmarks = [
    ("LM_01_head_top", "头顶", (0, 0, 1.75)),
    ("LM_02_chin", "下巴", (0, -0.05, 1.55)),
    ("LM_03_chest", "胸中心", (0, -0.05, 1.35)),
    ("LM_04_abdomen", "腹中心", (0, -0.03, 1.10)),
    ("LM_05_back", "背中心", (0, 0.10, 1.25)),
    ("LM_06_pelvis", "骨盆中心", (0, -0.02, 0.90)),
    ("LM_07_shoulder_L", "左肩", (-0.20, -0.05, 1.50)),
    ("LM_08_elbow_L", "左肘", (-0.50, -0.05, 1.50)),  # T-pose: 同肩高
    ("LM_09_wrist_L", "左腕", (-0.80, -0.05, 1.50)),   # T-pose: 同肩高
    ("LM_10_shoulder_R", "右肩", (0.20, -0.05, 1.50)),
    ("LM_11_elbow_R", "右肘", (0.50, -0.05, 1.50)),
    ("LM_12_wrist_R", "右腕", (0.80, -0.05, 1.50)),
    ("LM_13_knee_L", "左膝", (-0.10, -0.02, 0.50)),
    ("LM_14_ankle_L", "左踝", (-0.10, -0.02, 0.05)),
    ("LM_15_knee_R", "右膝", (0.10, -0.02, 0.50)),
    ("LM_16_ankle_R", "右踝", (0.10, -0.02, 0.05)),
]

for name, cn_name, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.02)
    empty = bpy.context.active_object
    empty.name = name
    empty.location = loc
    empty.color = (1.0, 0.2, 0.2, 1.0)  # 红色
    empty["cn_name"] = cn_name
```

### Step 2: 用户标记

用户在Blender GUI中移动空对象到正确位置：
- 按`G`移动，`1/3/7`切换视角
- 空对象应放在模型表面（可稍微陷入）
- 左右对称点应大致对称
- 关节放在弯曲处，不是肌肉凸起处

### Step 3: 读取坐标

```python
landmarks_3d = {}
for name, cn_name, _ in landmarks:
    empty = bpy.data.objects.get(name)
    if empty:
        landmarks_3d[cn_name] = empty.matrix_world.translation.copy()
```

## 16点位置说明

| 编号 | 名称 | 位置 | 推荐视角 |
|------|------|------|----------|
| 1 | 头顶 | 头部最顶端中心 | front/top |
| 2 | 下巴 | 下颌最底端中心 | front |
| 3 | 胸中心 | 胸口正中心 | front |
| 4 | 腹中心 | 腹部正中心（肚脐） | front |
| 5 | 背中心 | 背部正中心 | back |
| 6 | 骨盆中心 | 骨盆/裆部中心 | front |
| 7 | 左肩 | 左肩-手臂连接处 | front/top |
| 8 | 左肘 | 左肘弯曲处 | left/front |
| 9 | 左腕 | 左手腕-手掌连接处 | left/front |
| 10 | 右肩 | 右肩-手臂连接处 | front/top |
| 11 | 右肘 | 右肘弯曲处 | right/front |
| 12 | 右腕 | 右手腕-手掌连接处 | right/front |
| 13 | 左膝 | 左膝盖弯曲处 | front/left |
| 14 | 左踝 | 左脚踝连接处 | front/left |
| 15 | 右膝 | 右膝盖弯曲处 | front/right |
| 16 | 右踝 | 右脚踝连接处 | front/right |

## 初始位置计算（T-pose 修正版）

**关键修正 (2026-07-27)**: T-pose 手臂的肩/肘/腕必须在**同一 Z 高度**（~1.50m = 83% of 1.8m），不要按 A-pose 比例估算（82%/62%/42%）。

基于 bbox 比例（身高 H，Z 从 0 到 H）：
- 头顶： 0.97H
- 下巴： 0.86H
- 胸中心： 0.75H
- 腹中心： 0.61H
- 背中心： 0.69H
- 骨盆： 0.50H
- **肩： 0.83H, |X| = 0.11W**
- **肘： 0.83H, |X| = 0.28W**  ← T-pose 同肩高
- **腕： 0.83H, |X| = 0.44W**  ← T-pose 同肩高
- 膝： 0.28H, |X| = 0.06W
- 踝： 0.03H, |X| = 0.06W

## 优势

- **精确**：用户直接指定，比自动检测准（误差<1cm vs 30-50cm）
- **快速**：16个点10分钟标完
- **灵活**：可只标关键部位，忽略衣服干扰区域
- **可靠**：不受姿势差异（A-pose/T-pose）影响

## 适用场景

- A-pose模型（自动比例估算失效）
- 宽松衣服模型（拓扑分析被衣服干扰）
- 非标准体型（比例估算不适用）
- 快速原型验证（不想写复杂检测算法）

## 优化方案（2026-07-28 更新）

### 空对象优化
```python
for name, cn_name, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.015, location=loc)
    e = bpy.context.active_object
    e.name = name
    e.show_in_front = True      # 始终显示在最前面, 不被模型遮挡
    e.color = (1.0, 0.2, 0.2, 1.0)  # 红色
    e["cn_name"] = cn_name
```

### 模型不可选中（防止误移动）
```python
for obj in [mh_body, mh_head, tripo]:
    if obj:
        obj.hide_select = True
```

### Tripo参考模型默认隐藏
```python
tripo.hide_set(True)
tripo.hide_render = True
```
- 如需显示对照：在Outliner里点击眼睛图标，或按`/`键切换局部视图
- 避免其他人打开文件时看到两个模型而困惑

### 不要镜像
- 模型本身可能不对称, 镜像会导致错误
- 左右两边都手动标
- Blender `Ctrl+M` 对空对象位置无效（只镜像物体原点变换, 不镜像位置）

### MetaHuman坐标系（重要修正）
- MetaHuman原始就是脸朝-Y, 和Tripo一致, **不需要旋转**
- 早期脚本错误地绕Z-90°旋转, 导致脸朝-X
- 验证方法: 检查面部顶点(Y < -0.10)的中心, 如果Y为负说明脸朝-Y

### MetaHuman缩放（重要修正）
- MetaHuman matrix_basis自带0.01缩放(cm→m), **不要手动** `v.co *= 0.01`
- 直接 `transform_apply` 即可应用缩放
- 手动缩放+transform_apply会导致顶点坐标崩溃(重复缩放)

### 必须导入Body+Head
- Body alone: Z[0, 1.496m] (no head)
- Body+Head: Z[0, 1.803m]
- 必须按Body+Head总高缩放到1.8m, 只用Body会导致比例错误
