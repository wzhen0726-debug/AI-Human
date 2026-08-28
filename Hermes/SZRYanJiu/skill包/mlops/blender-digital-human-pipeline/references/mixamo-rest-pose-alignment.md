# 静止姿态对齐：行走动画开度问题的根因与修复 (2026-08-27)

> 用户判断"这个问题经常出现在静置姿态不同"——完全正确。
> 行走动画手臂开度、腿开度异常 → 根因是骨骼朝向/roll与Mixamo不一致。

## 诊断方法

逐骨对照我们的骨架 vs Mixamo参考骨架（同一FBX导入）：
```python
# 对每根同名骨：
mo = our_matrix_world @ bone.matrix_local  # 我们
mm = mixamo_matrix_world @ mix_bone.matrix_local  # 参考
y_o = mo.to_quaternion() @ Vector((0,1,0))  # 骨延伸方向
y_m = mm.to_quaternion() @ Vector((0,1,0))
ang = math.degrees(y_o.angle(y_m))  # 方向差
z_o = mo.to_quaternion() @ Vector((0,0,1))  # roll方向
z_m = mm.to_quaternion() @ Vector((0,0,1))
ang_z = math.degrees(z_o.angle(z_m))  # roll差
```
**验收标准**: 方向差 < 1° 且 roll差 < 1° 对所有同名骨。

## 修复方案A（用户选定）

骨骼朝向/roll**完全照抄Mixamo参考骨架的实测世界轴**，位置用用户打的点。

步骤：
1. 导入Mixamo参考FBX，测量每骨的**世界Y轴（延伸方向）和世界Z轴（roll方向）**
2. 保存为 `mixamo_rest_spec.json`（含每骨的 `y` 和 `z` 向量）
3. 重建骨架时，对每根骨：
   - `b.tail = b.head + y_dir * bone_length`（方向照抄）
   - `b.align_roll(z_dir)`（roll照抄）
4. 位置（head）来自用户打的标记点

```python
for b in edit_bones:
    sb = spec.get("mixamorig:" + b.name)
    if sb:
        y_dir = Vector(sb["y"]).normalized()
        b.tail = b.head + y_dir * b.length
        z_dir = Vector(sb["z"])
        b.align_roll(z_dir)
```

## 关键发现

1. **Mixamo FBX导入后世界轴已与模型同朝向**（都面朝-Y, Z-up），无需坐标映射。
   之前错误地做了 `map_vec` 坐标映射，导致方向全错。
2. **位置差是正常的**（模型比例不同），不影响动画——动画旋转靠的是局部轴向。
3. **验证**: 修复后方向差/roll差全部 0.00°（之前 47/52 骨有偏差）。
4. **行走测试通过**: 摆臂 8.5cm、脚贴地、2689/3000 顶点变形。

## 左右命名约定（重要！）

模型面朝 -Y 时：
- **+X 是模型的"左"侧**（从模型自身视角看）
- 用户标记的"右肩"在 +X = Mixamo 的 **Left** 系
- 所以：+X 侧标记 → Mixamo Left 命名，-X 侧 → Right 命名

## 眼球绑定（保留完整矩阵）

`parent_type=BONE` 时，必须保留**完整世界矩阵**（位置+旋转），不能只换算位置：
```python
tail_mat = Matrix.Translation((0, head_b.length, 0))
parent_mat = arm.matrix_world @ head_b.matrix_local @ tail_mat
M = o.matrix_world.copy()
o.parent = arm
o.parent_type = 'BONE'
o.parent_bone = 'Head'
o.matrix_basis = parent_mat.inverted() @ M  # 位置+旋转一次到位
```
只换算位置不换算旋转 → 虹膜被Head骨rest旋转带得朝下。

## 指骨生成规范

1. 指根**必须沿掌宽方向排开**，不能挤在同一点
2. 掌宽方向 = 模型前后轴（Y），拇指在前（-Y），小指在后（+Y）
3. 拇指方向 = 沿臂 + 前伸 + 下压：`(hand_dir + fwd*0.5 + Vector((0,0,-0.45))).normalized()`
4. 四指方向 = 沿手臂方向
