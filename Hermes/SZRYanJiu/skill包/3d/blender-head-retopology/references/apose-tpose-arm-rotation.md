# A-pose → T-pose 手臂旋转包裹失败分析

> 2026-07-28 test02 session: MetaHuman A-pose body wrap 到 Tripo T-pose 高模

## 核心问题

MetaHuman Body 是 A-pose（手臂下垂），Tripo 是 T-pose（手臂水平展开）。
直接 Shrinkwrap 会崩溃，旋转手臂后再 Shrinkwrap 也有问题。

## 三种失败模式（已验证）

### 失败模式 1：直接 Shrinkwrap 崩溃
- **现象**: X span 从 1.16m 骤降到 0.26m，模型完全压扁
- **根因**: MetaHuman A-pose（手臂下垂，X 窄） vs Tripo T-pose（手臂平伸，X 宽），Shrinkwrap 把手顶点拉向 Tripo 手臂，中间躯干被撕裂
- **结论**: 姿势差异 > 30° 时直接 Shrinkwrap 必然崩溃

### 失败模式 2：旋转后第二轮 Shrinkwrap 拉回
- **现象**: 旋转手臂到 T-pose 后，第二轮全身 Shrinkwrap 把手臂顶点拉回 A-pose 位置
- **精度**: 平均 65mm，最大 445mm
- **根因**: Shrinkwrap NEAREST_SURFACEPOINT 无方向性，只找最近表面，不管解剖对应关系
- **结论**: 旋转 + Shrinkwrap 组合无效，Shrinkwrap 会撤销旋转

### 失败模式 3：含衣服高模随机投射
- **现象**: 顶点投射到衣服表面而非身体，48% 顶点 |Z|>0.5（正常应 <0.2）
- **根因**: Tripo 含宽松衣服，衣服下无身体几何，Shrinkwrap 无语义理解
- **结论**: 未分离衣服的 AI 高模不能直接 Shrinkwrap

## v5 脚本硬编码失败分析（2026-07-28）

### 问题
`37_wrap_v5_arms.py` 硬编码肩膀位置：
```python
shoulder_L = Vector((0.04, -0.20, 1.50))  # 硬编码，非 landmark
```

未使用用户在 `landmark_scene_v6.blend` 中标的 16 个空对象。

### 连锁错误

| 错误 | 后果 |
|------|------|
| 距离阈值 `dL < 0.60` | 手部顶点（距离肩膀 ~0.64m）未被捕获，Y span 保持 1.4 |
| 阈值提高到 0.80 | 吞入躯干顶点（躯干 20228 → 13438），胸部/腰部被误旋转 |
| 旋转角度 45° | A-pose 实际下垂 ~45°，需转 90° 才能到 T-pose，45° 不足 |
| 未用 landmark | 旋转支点错误，手臂分类依据错误 |

### 验证数据

```
旋转前 MH bbox: X[-0.26,0.26] Y[-0.70,0.70] Z[0.00,1.80]
旋转后 MH bbox: X[-0.43,0.51] Y[-0.70,0.70] Z[0.00,1.80]  ← Y span 没变!
包裹后 MH bbox: X[-0.46,0.48] Y[-0.16,0.15] Z[0.00,1.80]  ← Y 被压扁
```

### 正确做法

1. **读取 landmark 空对象**: 从 `landmark_scene_mh_v1.blend` 读取用户标定的 16 个空对象
2. **用 landmark 作为旋转支点**: 不硬编码肩膀位置
3. **用 landmark 分类手臂**: 上臂（肩到肘）、前臂（肘到腕）、手（腕到指尖）
4. **旋转角度 90°**: A-pose 到 T-pose 需转 90°，不是 45°
5. **不用 Shrinkwrap**: 用 RBF/ARAP 变形或 Surface Deform

## MetaHuman Landmark 场景参数（2026-07-28 实测）

已创建 `landmark_scene_mh_v1.blend`，包含 MetaHuman Body + Tripo 参考 + 16 个空对象。

### 预填位置（基于 MetaHuman 实际几何分析，非估算）

| 空对象 | 预填位置 | 说明 |
|--------|----------|------|
| LM_07_shoulder_L | (0.01, -0.17, 1.50) | 三角肌中点，Y=-0.17 非 -0.20 |
| LM_08_elbow_L | (-0.03, -0.53, 1.30) | A-pose 下垂，Z 低于肩 |
| LM_09_wrist_L | (-0.19, -0.70, 1.13) | 手部，X 偏后 |
| LM_10_shoulder_R | (0.01, 0.17, 1.50) | 镜像 |
| LM_11_elbow_R | (-0.03, 0.53, 1.30) | 镜像 |
| LM_12_wrist_R | (-0.19, 0.70, 1.13) | 镜像 |

**关键发现**：MetaHuman A-pose 肘部 Z=1.30（低于肩 1.50），腕部 Z=1.13（低于肘）。T-pose 时三者同高 Z≈1.50。

### 几何分析数据

```python
# 左手(Y最小): (-0.194, -0.698, 1.126)
# 右手(Y最大): (-0.194, 0.698, 1.126)
# 左肩最接近点: (0.013, -0.173, 1.504)
# 左肘最接近点: (-0.031, -0.526, 1.304)
```

### 场景 UX 配置

- MetaHuman_Body: 灰色实体，hide_select=False
- Tripo_Reference: 半透明 (alpha=0.3)，hide_select=False
- 16 个空对象: SPHERE 类型，radius=0.015，show_in_front=True，红色 (1,0.2,0.2,1)

## MetaHuman 坐标系分析

绕 Z-90° 后：
- 原 X（肩宽）→ Y
- 原 Y（深度）→ -X
- 手臂在 Y 方向（A-pose 下垂时手在 ±Y）

分类条件：
```python
# 错误（硬编码）:
if dL < 0.60 and v.co.y < -0.12:  # 距离阈值太小，手捕获不到

# 正确（用 landmark）:
shoulder_L = Vector(landmarks['LM_07_左肩_shoulder_L'])
elbow_L = Vector(landmarks['LM_08_左肘_elbow_L'])
wrist_L = Vector(landmarks['LM_09_左腕_wrist_L'])

# 上臂: 距离肩 < 距离肘
# 前臂: 距离肘 < 距离腕
# 手: 距离腕 < 0.15
```

## 旋转矩阵验证（Blender 5.1）

```python
# 验证: (0, -1, 0) 左臂方向
Matrix.Rotation(+45°, 'Z') → (0.707, -0.707, 0)   # +X+Y 方向
Matrix.Rotation(-45°, 'Z') → (-0.707, -0.707, 0)  # -X-Y 方向
Matrix.Rotation(+90°, 'Z') → (1, 0, 0)            # +X 方向
Matrix.Rotation(-90°, 'Z') → (-1, 0, 0)           # -X 方向 ✓

# A-pose 手臂方向约 (-0.35, -0.35, 0)（45° 下垂）
# 要转到 (-1, 0, 0)（T-pose 水平向外）
# 需要旋转 45°，但 Blender -45° 实际效果是 +45°（方向相反）
# 所以用 Matrix.Rotation(-45°, 'Z') 实际得到 +45° 效果
```

## Blender append() 失效陷阱

`bpy.ops.wm.open_mainfile()` 会清空当前场景，所有对象引用失效。
之后 `bpy.ops.wm.append()` 追加对象时，不能用之前保存的对象变量名：

```python
# 错误: open_mainfile 后 mh_body 已失效
bpy.ops.wm.open_mainfile(filepath=MH_BLEND)
mh_body = ...  # 获取对象
bpy.ops.wm.save_as_mainfile(filepath=TMP_MH)

# 重新打开场景
bpy.ops.wm.open_mainfile(filepath=tmp_tripo)
# mh_body.name 此时 ReferenceError!

# 正确: 用硬编码名称字符串
MH_BODY_NAME = "NewMetaHumanCharacter_Body"
bpy.ops.wm.append(
    filepath=os.path.join(TMP_MH, "Object", MH_BODY_NAME),
    directory=os.path.join(TMP_MH, "Object"),
    filename=MH_BODY_NAME
)
mh_body = bpy.data.objects.get(MH_BODY_NAME)
```

## 结论：Shrinkwrap 不适合 A-pose → T-pose 全身包裹

含衣服的 AI 高模上，Shrinkwrap NEAREST 无法正确投射手臂：
1. 直接 Shrinkwrap → 手臂拉到躯干（崩溃）
2. 旋转后 Shrinkwrap 躯干 → 躯干 OK，但手臂无法后续投射
3. 旋转后 Shrinkwrap 全身 → 手臂被拉向最近衣服表面（变形）

**替代方案**：
- Surface Deform + 手动顶点组（手臂单独绑定到 Tripo 手臂）
- 接受躯干精度，手臂后续绑定时修正
- 先分离 Tripo 衣服和身体
- **RBF landmark 变形**（推荐，用用户标的 16 个 landmark）
