# GLB matrix_world / Local-World Coordinate Pitfall (2026-07-24)

## 问题现象

混元Apose (hunyuan001.glb) 修复流程全部 PASS（网格修复、黏连修复、QA），
但渲染截图连续 6+ 次全黑/全灰。相机 `dot(forward, to_model) = 1.000`
（正对模型），模型 hide_render=False、法线朝外、材质正常。

## 根因

**bbox 用 local 坐标计算，但混元 GLB 的 `obj.matrix_world` 自带 X 轴 -90° 旋转**：

```
obj.matrix_world:
  (1,  0,  0, 0)
  (0,  0, -1, 0)   <- local (x,y,z) -> world (x,-z,y)
  (0,  1,  0, 0)
  (0,  0,  0, 1)
```

| 坐标系 | y 范围 | z 范围 |
|--------|--------|--------|
| local (v.co) | [-0.121, 0.121] | [0, 1.163] |
| world (matrix_world @ v.co) | [-0.499, 0.499] | [-0.121, 0.121] |

相机按 local bbox 放在 `center.y - dist`，但 world 中模型在 y=[-0.5, 0.5]，
相机在 y=-1.4 看向 y=0 —— 模型大部分在视锥外或紧贴相机，渲染为空。

## 排查过程（6 次失败尝试）

1. 怀疑相机朝向 (`to_track_quat('-Z','Y')`) → dot=1.0 排除
2. 怀疑材质深色 → 断开纹理设 Base Color 0.7 → 仍全灰
3. 怀疑 WORKBENCH 光照 → 换 EEVEE → 仍全灰
4. 怀疑相机未持久化 → 加 `scene.collection.objects.link(cam)` → 仍全灰
5. 怀疑模型隐藏 → hide_render=False 排除
6. **检查 matrix_world → 发现 X 轴 -90° 旋转 → 根因确认**

## 修复

### render_screenshot.py：用 world 坐标计算 bbox

```python
# 错误: local 坐标
xs = [v.co.x for v in obj.data.vertices]

# 正确: world 坐标
world_verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
xs = [v.x for v in world_verts]
ys = [v.y for v in world_verts]
zs = [v.z for v in world_verts]
```

### repair.py：清除预旋转（关键新增）

混元模型 `matrix_basis` 非单位矩阵，`obj.rotation_euler = (0,0,0)` 无效——
matrix_basis 是最终存储值，必须显式重置：

```python
if abs(obj.matrix_world.to_euler().x) > 0.01 or abs(obj.matrix_world.to_euler().y) > 0.01:
    print(f"  Clearing pre-existing rotation: {obj.matrix_world.to_euler()}")
    bm = bmesh.new(); bm.from_mesh(obj.data)
    rot = obj.matrix_world.to_3x3()
    for v in bm.verts:
        v.co = rot @ v.co  # 应用旋转到顶点
    bm.to_mesh(obj.data); bm.free()
    # 重置对象变换 (matrix_basis 是存储值)
    obj.matrix_basis = Matrix.Identity(4)
    obj.data.update()
```

**清除后效果**：混元模型自然呈现 arms 沿 X、face 沿 -Y、height 沿 Z 的正确朝向，
无需额外躺姿旋转。

## 影响范围

所有读取 `v.co` / bmesh 局部坐标做世界空间判断的逻辑：
- render_screenshot.py 相机取景
- adhesion.py 排除区 (|X|>0.42, Z<0.10) — 在旋转模型上测错轴
- repair_qa.py bbox/身高检查
- 任何 raycast 反投影的相机参数计算

## 混元模型躺姿旋转方向 (2026-07-24 补充)

混元 GLB 原始朝向是**躺姿**（Y=身高, Z=身宽），但旋转方向容易搞错：

| 尝试 | 旋转 | 结果 |
|------|------|------|
| 错误 | 绕 X 轴 **-90°** (y→z, z→-y) | 模型变成**趴着**（-Y=身高, Z=身宽） |
| 正确 | 绕 X 轴 **+90°** (y→-z, z→y) | 模型**站立**（Z=身高, Y=身宽） |

**关键**：躺姿检测后，先绕 X 轴 +90° 站起，再检查 arms 是否沿 X。
如果 arms 还在 Y，再绕 Z 轴 90°。

**预旋转清除后**：混元模型自然呈现 arms 沿 X、face 沿 -Y、height 沿 Z，
无需额外旋转。`rotate_to_standard` 的躺姿分支只在未清除预旋转时触发。

## 检测清单

渲染全黑时按序排查：
1. pixel 统计确认背景色占比 >95%
2. `dot(cam_forward, to_model)` 是否 ≈1.0
3. `obj.matrix_world` 是否单位矩阵
4. world bbox vs local bbox 是否一致
5. 模型 hide_render / 材质 / 光照

**前三项任何一项异常，优先修复坐标系问题，不要动材质/光照。**

## 相关模型特性

| 模型 | matrix_world | 原始朝向 | 清除预旋转后 | 额外旋转 |
|------|-------------|---------|-------------|---------|
| tripoTpose | 单位矩阵 | T-pose 站立 | 无需处理 | 无 |
| tripoApose | 单位矩阵 | A-pose 站立 | 无需处理 | 无 |
| 混元Apose | X 轴 -90° 旋转 | 躺姿 (Y=身高, Z=身宽) | 自然站立，arms 沿 X | 无（清除后已正确） |