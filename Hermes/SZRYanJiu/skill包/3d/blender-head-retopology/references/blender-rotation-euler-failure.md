# Blender 5.1 rotation_euler 失效陷阱

> 2026-07-27~28 test02 session: 设置 rotation_euler 后 matrix_world 不更新

## 问题

Blender 5.1 中，设置 `mesh_obj.rotation_euler` 后：
- `matrix_world` **不更新**（仍然是单位矩阵）
- `transform_apply(rotation=True)` **不应用旋转**（顶点坐标不变）
- 但 `rotation_euler` 属性本身显示已设置

## 复现

```python
import bpy, math

# 假设 mesh_obj 已导入且为活动对象
mesh_obj.rotation_euler = (0, 0, math.radians(-90))
bpy.context.view_layer.update()

# 检查
print(mesh_obj.rotation_euler)  # (0, 0, -1.5708) — 已设置
print(mesh_obj.matrix_world)    # 单位矩阵 — 未更新！

# 应用
bpy.ops.object.transform_apply(rotation=True)
print(mesh_obj.data.vertices[0].co)  # 与原始相同 — 未旋转！
```

## 解决方案：使用 `matrix_basis` 直接旋转

```python
from mathutils import Matrix
import math

# 正确方法：直接修改 matrix_basis
rot = Matrix.Rotation(math.radians(-90), 4, 'Z')
mesh_obj.matrix_basis = rot @ mesh_obj.matrix_basis
bpy.context.view_layer.update()

# 检查
print(mesh_obj.matrix_world)  # 已更新，包含旋转

# 应用
bpy.ops.object.transform_apply(rotation=True)
print(mesh_obj.data.vertices[0].co)  # 已旋转！
```

## 验证方法 — 必须用 vision_analyze，不能只看顶点坐标

旋转后**必须渲染截图并用 vision_analyze 确认朝向**：

```python
# 1. 渲染 front/left/top 三视图
# 2. 用 vision_analyze 确认："人物是站着的还是躺着的？头顶朝哪个方向？"
# 3. 只有 vision 确认"站着、头朝上"才算成功
```

**为什么不能只看顶点坐标或 bbox？**
- Tripo 模型身高(~0.976m)和手臂展开(~0.981m)尺寸接近
- 旋转后 bbox 的 X 和 Z span 几乎相同（1.79 vs 1.80）
- 顶点坐标分析多次得出错误结论（误以为旋转成功，实际仍躺着）
- **vision_analyze 是唯一可靠的朝向验证方法**

## 正确旋转组合（2026-07-28 确认，v5）

Tripo GLB 原始朝向：Y=身高(躺，0~0.976m)，Z=手臂展开(±0.49m)，X=厚度(±0.085m)。
通过极值点分析确认：Y最大点(0, 0.976, 0)是头顶，Y=0是脚底，Z=±0.49且Y=0.775是两手腕(T-pose)。

目标朝向：Z=身高(头朝上)，X=宽度(T-pose手臂)，Y=深度(正面朝-Y)。

**正确旋转：绕X轴-90° + 绕Z轴-90° + 绕Y轴-90°**（三步，用matrix_basis）

```python
# Step 1: 绕X轴-90° — 使Y(身高躺)→Z(身高站)
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'X') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)

# Step 2: 绕Z轴-90° — 使Z(手臂)→X(宽度)，X(厚度)→-Y(正面朝-Y)
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Z') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)

# Step 3: 绕Y轴-90° — 交换X和Z（修正两步后的X/Z错位）
mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, 'Y') @ mesh_obj.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(rotation=True)
```

**vision_analyze 确认结果（v5）**：
- front视图：人物**站着**，T-pose手臂水平展开，头顶朝**上** ✓
- left视图：人物**站着**，侧面，头顶朝**上** ✓

**最终bbox**：X=1.81m(手臂展开), Y=0.31m(厚度), Z=1.80m(身高)，脚接地Z=0。

## v4 vs v5 对比（关键教训）

| 版本 | 旋转组合 | bbox X/Z | vision_analyze 结果 | 问题 |
|------|---------|----------|-------------------|------|
| v4 | 绕X-90° + 绕Z-90° (两步) | X=1.79, Z=1.80 | **横躺着，头朝右** ❌ | X=身高, Z=手臂(错位) |
| v5 | 绕X-90° + 绕Z-90° + 绕Y-90° (三步) | X=1.81, Z=1.80 | **站着T-pose，头朝上** ✓ | 修正X/Z错位 |

**核心教训**：两步旋转后 X=身高/Z=手臂（X和Z错位），因为绕X轴旋转后手臂在Z方向，绕Z轴旋转把手臂转到X但身高也跟着转了。第三步绕Y轴-90°交换X和Z才修正。

**bbox 无法区分 v4 和 v5**——两者的 X/Z span 几乎相同（1.79 vs 1.81, 1.80 vs 1.80），只有 vision_analyze 能区分。

## 之前失败的旋转组合（不要重试）

- ❌ 绕X轴+90° + 绕Z轴+90°：头朝下
- ❌ 绕Z轴-90° + 绕Y轴+90°：身高留在Y方向(还是躺姿)
- ❌ 绕X轴-90° + 绕X轴180° + 绕Z轴180°：左右互换+正面朝后
- ❌ 绕X轴-90° + 绕Z轴-90°（两步）：X和Z错位，模型仍横躺
- ❌ bmesh手动旋转顶点：逻辑正确但容易出错，且与matrix_basis方法混用导致混乱
- ❌ 只看bbox尺寸验证：对称模型旋转后尺寸可能不变，必须用vision_analyze

## 通用旋转推导方法（适用于任意朝向的模型）

不要凭直觉或试错旋转。按以下步骤推导：

### Step 1：分析原始朝向

用极值点定位头顶/脚底/手腕，确定哪个轴是身高/宽度/厚度：

```python
import numpy as np
# 从GLB读取顶点
pos = ...  # (N, 3) array
print(f'X: {pos[:,0].min():.3f} to {pos[:,0].max():.3f}')
print(f'Y: {pos[:,1].min():.3f} to {pos[:,1].max():.3f}')
print(f'Z: {pos[:,2].min():.3f} to {pos[:,2].max():.3f}')

# 找极值点
y_max_idx = np.argmax(pos[:,1])  # 身高最大值
print(f'Y最大点: {pos[y_max_idx]}')  # 如果是头顶 → Y=身高
```

### Step 2：确定目标映射

目标统一为：Z=身高(头朝上), X=宽度(T-pose手臂), Y=深度(正面朝-Y)

根据原始朝向确定映射关系，如：
- 原Y(身高) → 新Z
- 原Z(手臂) → 新X
- 原X(厚度) → 新Y

### Step 3：分解为单轴旋转

从映射关系推导旋转组合。每个 `Matrix.Rotation(angle, 4, axis)` 对应一个轴交换。

**注意**：Blender 5.1 的 `Matrix.Rotation(-90, X)` 实际产生逆时针+90°旋转（与数学约定可能相反），需通过顶点坐标验证。

### Step 4：渲染截图并用 vision_analyze 验证

```python
# 渲染front图
cam.location = center + Vector((0, -cam_dist, 0))
# vision_analyze: "人物是站着的还是躺着的？头顶朝哪个方向？"
```

**不要只看 bbox 或顶点坐标**——对称模型旋转后尺寸可能不变，只有 vision_analyze 能区分。

### Step 5：如果 vision 说还是错的

分析当前 X/Y/Z 分别对应什么（身高/手臂/厚度），找到错位的轴对，用额外旋转修正。

## 处理不同原始朝向的模型

| 原始朝向 | 身高轴 | 旋转策略 |
|---------|--------|---------|
| Y=身高(躺) | Y | 绕X-90° + 绕Z-90° + 绕Y-90°（三步） |
| X=身高(头朝右) | X | 绕Y轴旋转使X→Z，再调整手臂/正面 |
| Z=身高(头朝下) | Z | 绕X轴180°翻转使头朝上 |
| 已正确(Z=身高,头朝上) | Z | 不旋转，直接缩放接地 |

**关键**：先用极值点分析确定原始朝向，再查表选旋转策略，最后用 vision_analyze 验证。
