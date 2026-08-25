# Rotation Correction Algorithm v3 — foot_score

> Verified 2026-07-31 on Blender 5.1 + Tripo AI GLB (1.93M face, raw_model.glb).  
> User iteration: 3 rounds of modify→vision-check.  
> Visual confirmation: standing, face toward -Y, T-pose.

## Problem: T-pose臂展≈身高, bbox无法区分

用户旋转 raw_model.glb 后, 输出模型在 Blender 中是躺着的. bbox dims 显示:
```
x=1.801, y=0.313, z=1.810  →  X≈Z, 无法区分臂展和身高
```

旧算法（_ensure_stand_up 用"bbox最大维度=身高轴"或"底部顶点分布最集中"）都失效:
- bbox最大维度: X=1.801 和 Z=1.810 几乎相等, 无法区分
- 脚底分布: 手脚分布相似, 误判已站立

## Solution: foot_score 判据

身高轴 ≠ 最大轴. 对每根候选轴, 比较其两端1%顶点的横截面积.

### 核心原理

- 脚底端(脚+小腿)横截面积 > 手腕端(手掌)
- 身高轴 = "低端面积 - 高端面积"差值最大的轴（脚在低端）
- 实测: foot_scores x=-0.000, y=-0.583, **z=+0.097** → 正确识别身高沿Z(已站立)

### 实现

```python
def end_area(axis_vals, other1, other2, at_low):
    """计算轴两端1%顶点的横截面积（在另外两轴上的分布范围乘积）"""
    s = sorted(axis_vals)
    n = max(200, len(s)//100)
    t = s[n] if at_low else s[-n]
    o1 = [v for v, a in zip(other1, axis_vals) if a <= t] if at_low else [v for v, a in zip(other1, axis_vals) if a >= t]
    o2 = [v for v, a in zip(other2, axis_vals) if a <= t] if at_low else [v for v, a in zip(other2, axis_vals) if a >= t]
    if not o1 or not o2:
        return 0
    return (max(o1)-min(o1)) * (max(o2)-min(o2))

def foot_score(axis_vals, o1, o2):
    lo = end_area(axis_vals, o1, o2, True)   # 低端面积
    hi = end_area(axis_vals, o1, o2, False)  # 高端面积
    return lo - hi  # 正值越大, 低端越像脚（腿粗脚大）

scores = {
    "X": foot_score(xs, ys, zs),
    "Y": foot_score(ys, xs, zs),
    "Z": foot_score(zs, xs, ys),
}
height_axis = max(scores, key=scores.get)  # foot_score最大的轴=身高轴
```

### 脚端正负判定

确定身高轴后, 还需要知道脚在正端还是负端, 以便旋转时把脚转到-Z:

```python
def foot_at_low(axis_vals, o1, o2):
    """脚底端横截面积更大的那端是脚"""
    return end_area(axis_vals, o1, o2, True) > end_area(axis_vals, o1, o2, False)
```

### 旋转方向选择

| 身高轴 | 脚在低端 | 旋转变换 | 说明 |
|--------|---------|---------|------|
| X | 是(-X→脚) | x→z, z→-x | 绕Y轴+90°, 脚-X→脚-Z |
| X | 否(+X→脚) | x→-z, z→x | 绕Y轴-90°, 脚+X→脚-Z |
| Y | 是(-Y→脚) | y→z, z→-y | 绕X轴-90°, 脚-Y→脚-Z |
| Y | 否(+Y→脚) | y→-z, z→y | 绕X轴+90°, 脚+Y→脚-Z |
| Z | — | 不动 | 已站立 |

## Pitfalls — numpy 实现 (2026-08-05 重写后 ad-hoc 逻辑验证抓到的真bug)

### 1. 元组赋值视图别名 (列交换旋转的核心坑)

```python
x, y, z = arr[:, 0], arr[:, 1], arr[:, 2]
arr[:, 1], arr[:, 2] = -z, y   # ❌ y 是 arr[:,1] 的视图, 第二次赋值时 arr[:,1] 已被覆盖
```

任何 numpy 列交换旋转 (x+90 / y-90 / z+90) 必须先 `.copy()`:

```python
x, y, z = arr[:, 0].copy(), arr[:, 1].copy(), arr[:, 2].copy()
```

注意: bmesh 里 `v.co.x, v.co.y = v.co.y, -v.co.x` 是安全的 (属性赋值无视图别名), 只有 numpy 批量列赋值有此问题。

### 2. numpy 2.x 移除了 `ndarray.ptp()` 方法

Blender 5.1 自带 numpy 2.3.4, 系统 numpy 2.4.3 — `coords[:, a].ptp()` 在两个环境都崩。统一用 `np.ptp(coords[:, a])` (1.x/2.x 通用)。

### 3. 断言陷阱: 臂展 ≥ 身高是解剖学正常

T-pose 臂展 (X=1.810) 可合法大于身高 (Z=1.708)。测试/验证时**不要断言** `height == max(dims)`; 正确不变量是 foot_score 自身判定 Z 为身高轴 — 这正是 foot_score 存在的目的。

### 无 Blender 的 mock 验证法 (系统 Python 直跑)

旋转/foot_score 是纯 numpy 逻辑, 不必开 Blender 即可验证: mock 一个 obj, 暴露 `data.vertices` (支持 `foreach_get`/`foreach_set`/`__len__`/`__iter__` yield `v.co.x/y/z`)、`matrix_world.to_euler()`、`data.update()`, 用 importlib 加载 repair.py 并 stub 掉 bpy。合成合成人形的解剖要点: 躯干深度 (y 半径) 必须随身高变化 (低处臀突、高处胸突、中部腰收) — 平背柱贯穿全高会让 foot_score 退化误判。验证后临时脚本要删掉。

## Face Direction Detection (鼻部突出度)

纯几何方法, 不依赖AI:

```python
def _detect_face_direction(obj):
    """通过鼻部突出度检测面朝向"""
    mn, mx, dims = get_bbox(obj)
    z_face = mn[2] + dims[2] * 0.85  # 面部区域(头顶15%)
    
    fx = [v.co.x for v in obj.data.vertices if v.co.z >= z_face]
    fy = [v.co.y for v in obj.data.vertices if v.co.z >= z_face]
    if not fx: return None
    
    import statistics
    med_x = statistics.median(fx)
    med_y = statistics.median(fy)
    
    protrusions = {
        '+X': max(fx) - med_x,  # +X突出度(鼻尖/后脑在+X的突出)
        '-X': med_x - min(fx),
        '+Y': max(fy) - med_y,
        '-Y': med_y - min(fy),
    }
    return max(protrusions, key=protrusions.get)  # 突出度最大的方向=面朝方向
```

### 旋转到目标方向(-Y)

```python
def _rotate_to_negY(obj, current_dir):
    """绕Z轴旋转, 使当前面朝current_dir的模型转到面朝-Y"""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    if current_dir == '+X':     # 绕Z轴顺时针90°
        for v in bm.verts: v.co.x, v.co.y = v.co.y, -v.co.x
    elif current_dir == '-X':   # 绕Z轴逆时针90°
        for v in bm.verts: v.co.x, v.co.y = -v.co.y, v.co.x
    elif current_dir == '+Y':   # 绕Z轴180°
        for v in bm.verts: v.co.x, v.co.y = -v.co.x, -v.co.y
    # '-Y' → 不需要旋转
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
```

**关键**: `+Y` 分支必须旋转180° (v.co.x=-v.co.x; v.co.y=-v.co.y), 不能是 pass. 初始版本误把 direction 当成目标方向而非当前方向, +Y 分支写成了 pass, 导致面朝+Y时模型未旋转.

## 三步旋转流程 (rotate_to_standard)

```python
def rotate_to_standard(obj):
    # 0. 清除 matrix_world 预旋转(混元模型自带X-90°)
    if abs(obj.matrix_world.to_euler().x) > 0.01 or abs(obj.matrix_world.to_euler().y) > 0.01:
        bm = bmesh.new(); bm.from_mesh(obj.data)
        rot = obj.matrix_world.to_3x3()
        for v in bm.verts: v.co = rot @ v.co
        bm.to_mesh(obj.data); bm.free()
        obj.matrix_basis = Matrix.Identity(4)
        obj.data.update()
    
    # 1. 确保站立 (身高沿Z) — 可能需要多轮旋转
    for _ in range(3):
        if not _ensure_stand_up(obj): break
    
    # 2. 确保手臂沿X (dim_x > dim_y * 1.5)
    _ensure_arms_along_x(obj)
    
    # 3. 检测面朝向并旋转到-Y
    face_dir = _detect_face_direction(obj)
    if face_dir:
        _rotate_to_negY(obj, face_dir)
```

## 验证方法

旋转算法改完必须**渲染 + vision_analyze 确认**三要素, 不能只看 bbox dims:

1. **站立**: 头在上(Z最高), 脚在下(Z最低)
2. **面朝-Y**: 从-Y方向渲染看到脸(鼻子/眼睛), 从+Y方向看到后脑
3. **T-pose**: 手臂沿X向两侧水平伸展

渲染脚本:
```python
cam.location = Vector((cx, cy - h*1.5, cz))  # 从-Y看
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
```

## 历史

| 版本 | 日期 | 判据 | 问题 |
|------|------|------|------|
| v1 | 2026-07-27 | bbox最大维度=身高轴 | 躺姿(dim_y>dim_x)时绕X站起, 但T-pose臂展≈身高时失效 |
| v2 | 2026-07-31 | 底部1%顶点分布最广=身高轴 | 手脚分布相似, 无法区分 |
| v3 | 2026-07-31 | **foot_score**(低端面积-高端面积) | 正确识别臂展≠身高, 视觉验证通过 |