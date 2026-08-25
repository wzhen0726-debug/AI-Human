# MetaHuman Landmark 场景创建要点 (2026-07-28)

## 关键教训

### 1. Body + Head 必须一起导入

MetaHuman 低模 `Metahuman_Low_01.blend` 含 3 个独立网格：
- **Body**: Z -0.188~149.377 (cm，身高~150cm)
- **Head**: Z 141.668~180.309 (颈部以上，和 Body 有重叠)
- **Face**: 眼睛/牙齿等独立组件

**只导入 Body 会导致"没头的身子"**（用户原话）。正确做法：同时导入 Body + Head，总高 1.805m，一起缩放到 1.8m。

### 2. matrix_basis 自带 0.01 缩放 — 不要重复缩放

`Metahuman_Low_01.blend` 中 Body/Head 的 `matrix_basis` 自带 0.01 缩放（cm→m），顶点坐标已经是米单位。

**错误做法**:
```python
for v in body.data.vertices: v.co *= 0.01  # 重复缩放!
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # 顶点崩溃
```

**正确做法**:
```python
# 直接 transform_apply 应用 matrix_basis 的缩放
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
```

### 3. MetaHuman 原始朝向就是脸朝 -Y — 不需要旋转

MetaHuman 原始坐标系：X=肩宽（左右），Y=深度（前后），Z=身高（上下），脸朝 -Y。

**和 Tripo 一致，不需要绕 Z-90° 旋转**。之前错误地绕 Z-90° 旋转导致：
- 脸朝 -X（错误）
- 手臂从 X 方向转到 Y 方向（错误）

A-pose 手臂本来就在 X 方向（左右展开），旋转后到了 Y 方向（前后），完全错误。

### 4. 坐标系统一 — 直接缩放对齐即可

Tripo 和 MetaHuman 原始坐标系一致（都是 X=左右，Y=前后，Z=上下，脸朝 -Y）。

| | MetaHuman (A-pose) | Tripo (T-pose) |
|---|---|---|
| X span | 1.16m（肩宽+手臂厚度） | 1.81m（手臂展开） |
| Y span | 0.42m（身体+手臂前后厚度） | 0.31m（身体厚度） |
| Z span | 1.80m | 1.80m |

这是 A-pose vs T-pose 的正常差异，不需要旋转对齐。

### 5. 空对象预填位置（基于实际几何分析）

MetaHuman A-pose 实际位置（不旋转）：
- 左肩: (-0.17, -0.04, 1.50) — 三角肌中点
- 左肘: (-0.45, -0.04, 1.30) — A-pose 下垂，Z 低于肩
- 左腕: (-0.65, -0.10, 1.13) — A-pose 下垂，Z 低于肘
- 右肩: (0.17, -0.04, 1.50)
- 右肘: (0.45, -0.04, 1.30)
- 右腕: (0.65, -0.10, 1.13)

**关键发现**: A-pose 肘部 Z=1.30（低于肩），腕部 Z=1.13（低于肘）；T-pose 时三者同高 Z≈1.50。

### 6. 场景 UX 要求（2026-07-28 用户反馈）

- **模型不可选中**：`mesh_obj.hide_select = True`，防止误移动
- **参考模型默认隐藏**：Tripo 设 `hide_set(True)` + `hide_render = True`，避免混淆。用户说："这个文件中还有个 tripo的模型是用来做啥的，还是默认显示的，我怕其他人会误会"
- **不要镜像对称**：用户明确否定："算了 镜像不要了。我的模型也可能就是不堆成的"。模型本身可能不对称，镜像会导致错误。左右两边都手动标。

## 创建脚本模板

见 `scripts/create_landmark_scene.py`（可复用模板，支持任意 GLB 输入）。
