# Marker-based Rig → Mixamo Alignment (2026-08-27 四大根因修复)

手写版骨骼绑定（`rig_from_markers.py`，从用户标记点生成 Mixamo 65 骨命名骨架）在 GUI 检查中暴露四个错误，全部根因修复并数值验证。**任何"从标记点建骨架再套 Mixamo 动画"的场景都必须读本文。**

## 错误1: 眼球虹膜朝下 — BONE 父级必须保留完整世界矩阵

**症状**: 眼球位置正确但瞳孔朝地（虹膜方向实测 (0,-0.13,-0.99)，应为 (0,-1,0) 朝前）。
**根因**: `parent_type='BONE'` 时只换算了位置（`o.location = parent_mat.inverted() @ world_pos`），**没换算旋转**。Head 骨的 rest 旋转（非竖直骨骼 → matrix_local 带俯仰角）把子对象带动旋转。
**修复**: 用 matrix_basis 一次保留整个世界矩阵（位置+旋转）：
```python
tail_mat = mathutils.Matrix.Translation((0, head_b.length, 0))
parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
M = o.matrix_world.copy()
o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = 'Head'
o.matrix_basis = parent_mat.inverted() @ M
```
**验证**: 虹膜方向 = `(o.matrix_world.to_3x3() @ Vector((0,-1,0))).normalized()` 应 = (0,-1,0)。

## 错误2: 手指骨挤在一点 — 指根必须沿掌宽展开

**症状**: 五指指根全部重叠（y 坐标跨度仅 1cm），手指无法独立控制。
**根因**: 指根全放在 `wr + hand_dir*0.075`（同一个点），没有沿掌宽方向排开。
**修复**（T-pose 掌心朝下、模型面朝 -Y 时掌宽方向 = 世界 Y 轴）：
```python
fwd = Vector((0, -1, 0))  # 模型前方
# (名, 沿臂距离, 掌宽侧偏, 指长[3节]) — 拇指在前方侧, 小指在后方侧
fingers = [("Thumb",0.040,-0.048), ("Index",0.075,-0.022),
           ("Middle",0.078,0.000), ("Ring",0.075,0.020), ("Pinky",0.070,0.038)]
fbase = wr + hand_dir * along + fwd * side_off
```
拇指方向 = `hand_dir + fwd*0.50 + Vector((0,0,-0.45))` 归一化（Mixamo 实测 (0.77,-0.45,-0.45)：沿臂+朝前+朝下）。四指沿臂方向。
**验证**: 五个指根 y 跨度 ≈ 0.09m（真实掌宽）。

## 错误3: 骨骼 roll 反 180° → 动画旋转全部反相（手臂举头顶/小腿反折）

**症状**: 行走动画播放时双臂高举过头、小腿朝前反折；数值验证帧18 左手 z=1.97（头顶）。
**根因**: 动画 F 曲线的旋转在**骨骼局部坐标系**求值。我们四肢骨的局部 Z 轴与 Mixamo 约定相反（我们的朝上/朝后，Mixamo 朝下/朝前）→ 同一个四元数旋转在反相的局部系里效果反向。躯干骨（竖直方向）恰好两边一致所以躯干正常，四肢全错。
**权威修复方法**: **从 Mixamo T-Pose FBX 直接做世界系测量**（把 Mixamo 骨架导入后与我们的骨架同朝向：面朝 -Y、左 +X、上 +Z，逐骨 dump `matrix_world @ matrix_local` 后的 Z 轴方向），**不要按 armature 对象旋转欧拉角推导坐标系映射**——推导版实测把手臂 roll 目标搞错（z=1.62 偏高），世界系实测版正确（z=1.17 腰侧）。

Mixamo T-Pose 世界系实测目标（`b.align_roll(target)`）：
| 骨骼 | roll 目标 Z 方向 | 说明 |
|---|---|---|
| Arm / ForeArm / Hand | (0, 0, -1) | Z 朝下 |
| UpLeg / Leg | (0, -1, 0) | Z 朝前 |
| Foot | (-0.05, -0.46, 0.89)（右侧 x 取反） | Z 朝上前 |
| ToeBase | (0, 0, 1) | Z 朝上 |
| 四指 1-3 | (0, 0, -1) | 同手臂 |
| Thumb 1-3 | Left(-0.5,0,-0.87) / Right(0.5,0,-0.87) | 朝下偏身侧 |
| 躯干 Hips/Spine/Neck/Head | 不动 | 实测已一致 |

**脚骨结构修正**（同源问题）: Foot 必须**踝→趾根（朝前）**，不能踝→脚跟（朝后）。趾根 = 踝 + fwd*0.16 + (0,0,-0.06)；ToeBase = 趾根→趾尖 fwd*0.23。
**验证数值**（Standard Walk 帧1 vs 帧18）: 左手 z ∈ 1.0~1.6（腰侧摆臂）、位移 >2cm；右脚 z < 0.4（贴地）；mesh 变形（depsgraph）>2000/3000。

## 错误4: 左右命名镜像 — 面朝 -Y 时 +X 是模型 LEFT

**根因**: Mixamo 命名以**模型自身**视角定左右。模型面朝 -Y 时，+X 侧 = 模型的**左**侧。但用户打点时说的"右肩"（屏幕右侧 = +X）实际是模型的左肩。把 +X 标记建成 RightArm → 动画驱动时左右整体镜像（手臂交叉/拧转）。
**修复**: 用户"右肩/右肘/右腕/右膝/右踝"标记（+X 侧）→ Mixamo `Left*` 骨名；-X 侧镜像点 → `Right*`。
```python
for side, pre in [("R2L", "Left"), ("L2R", "Right")]:
    src = "R" if side == "R2L" else "L"   # 标记R侧(+X) → Left骨
```
**验证**: `LeftArm.head_local.x > 0` 且 `RightArm.head_local.x < 0`。

## 行走测试文件的两个额外根因

1. **测试脚本打开错文件**: 旧 `walk_test_fix.py` 打开的是 ARP 版 rig（`06_rig_arp_mixamo.blend`）而非手写版——复制脚本时 RIG 路径没改。交付前 grep 一遍脚本里的 blend 路径。
2. **slot 绑定必须找装数据的 slot**: Blender 5.x 复制 action 后可能出现多个 slot，`animation_data.action_slot = slots[0]` 不一定是装 fcurves 的那个（实测绑到空 slot handle=143 而数据在 142 → 骨骼全 (0,0,0)、mesh 零变形）。正确做法：遍历 `action.layers[].strips[].channelbags`，找 `len(bag.fcurves)>0` 的 `bag.slot_handle`，绑到对应 slot。
3. 交付文件里**删除 Mixamo 参考模型**（Alpha_Joints/Alpha_Surface/参考 Armature）——否则动画同时驱动参考模型，用户看到"动作只在参考上"。

## 交付验收清单（手写版）

- [ ] 虹膜 (0,-1,0) 朝前
- [ ] 指根 y 跨度 ≈0.09m，拇指朝前下
- [ ] LeftArm.x>0 / RightArm.x<0
- [ ] 姿态纯净（所有 pose bone 单位变换）
- [ ] 权重覆盖 100%
- [ ] 行走帧18：左手 z 1.0~1.6、右脚 z<0.4、mesh 变形>60%（depsgraph 求值）
- [ ] 文件里无 Mixamo 参考模型