# Mixamo骨骼对齐标准 (2026-08-25, 从用户提供的T-Pose.fbx提取)

## 权威参考文件
`原始模型/Mixamo动画文件/T-Pose.fbx` (65骨骼) + `Standard Walk.fbx` (行走测试动画)
提取结果存于 `05骨骼绑定/A_半自动打点/mixamo_reference.json`

## Mixamo标准：65根骨骼（不是22根！）
手写版之前只有22根主干骨骼，**缺手指/脚指细节**。Mixamo完整结构：

### 主干 (6根)
Hips → Spine → Spine1 → Spine2 → Neck → Head → HeadTop_End

### 手臂每侧 (5根×2=10根)
Shoulder → Arm → ForeArm → Hand（注意：**没有上臂/下臂命名，直接Arm/ForeArm**）

### 手指每侧 (20根×2=40根)
每指4节：Thumb1-4, Index1-4, Middle1-4, Ring1-4, Pinky1-4
**命名规则**: `{Left|Right}Hand{Thumb|Index|Middle|Ring|Pinky}{1-4}`

### 腿每侧 (4根×2=8根)
UpLeg → Leg → Foot → ToeBase（注意：**没有大腿/小腿命名，直接UpLeg/Leg**）

### 总计: 6+10+40+8 = 64 + Hips = 65

## 命名前缀
所有骨骼带 `mixamorig:` 前缀（Blender导入时保留）：
- `mixamorig:Hips`, `mixamorig:Spine`, ..., `mixamorig:LeftHandThumb1`

## 对齐要求（用户明确）
> "需要对齐mixamo的骨骼数量及骨骼名称，是为了之后方便我做重映射或者做管理"

- 手写版和ARP版都必须产出65根骨骼、`mixamorig:`前缀命名
- 骨骼数量/名称不一致 → 无法直接应用Mixamo动画（如Standard Walk）
- 行走动画测试：绑定好的角色应能播放 `Standard Walk.fbx` 的动作

## 长度参考（单位：Blender米，即厘米×0.01）
- Spine: 0.117, Spine1: 0.135, Spine2: 0.123, Neck: 0.108, Head: 0.196
- Shoulder: 0.129, Arm: 0.274, ForeArm: 0.276, Hand: 0.110
- UpLeg: 0.089, Leg: 0.434, Foot: 0.089, ToeBase: 0.069
- 手指各节: 0.026-0.047（见mixamo_reference.json完整值）
