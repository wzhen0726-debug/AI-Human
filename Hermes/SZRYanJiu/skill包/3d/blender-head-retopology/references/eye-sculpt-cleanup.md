# 眼部睫毛残留雕刻清理 — 详细技术参考

## 问题定义

Tripo/混元 AI 生成的高模在下眼睑（卧蚕）区域有尖锐凸起（睫毛残留），
高度 0.3-0.94mm，属于 AI 生成伪影，需清理。

## 技术方案

### 1. Vision 定位 → 像素坐标

渲染眼部特写（1200×900，85mm 长焦，cavity 开启增强细节），
用 vision_analyze 标记凸起像素坐标。

**视角选择**：
- slight_top：微俯，看卧蚕下方（最敏感视角）
- right45：右 45°，看右眼下睑
- front：正面，整体评估

**坐标系**：图像左上角为原点，X 向右，Y 向下。

### 2. 相机反投影 → 3D 射线

```python
# 相机参数（与渲染脚本一致）
cam_lens = 85  # mm
cam_sensor = 36  # mm
fov = 2 * atan(cam_sensor / (2 * cam_lens))  # ~23.9°

# 每个 vision 标记 → 世界空间射线
ndc_x = (2 * px / IMG_W) - 1
ndc_y = 1 - (2 * py / IMG_H)
half_h = tan(fov / 2)
half_w = half_h * (IMG_W / IMG_H)
ray_dir = (forward + right * ndc_x * half_w + up * ndc_y * half_h).normalized()
```

### 3. BVH Raycast → 表面命中点

```python
from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromBMesh(bm)
hit, normal, face_idx, dist = bvh.ray_cast(cam_pos, ray_dir, 0.5)
```

**注意**：`ray_cast` 只接受位置参数，无 `distance=` 关键字。

### 4. 尖峰检测

```python
# 候选区：反投影点 8mm 半径内（覆盖睑缘）
candidate_verts = {v.index for v in bm.verts 
                   if (v.co - hit).length < 0.008}

# 尖峰判据
for vi in candidate_verts:
    v = bm.verts[vi]
    neighbors = [e.other_vert(v) for e in v.link_edges]
    avg_pos = sum(n.co for n in neighbors) / len(neighbors)
    offset = v.co - avg_pos
    height = offset.length
    
    if height > 0.0002:  # >0.2mm 凸起
        peaks.append((vi, height, v.co, v.normal))
    elif height > 0.00015 and offset.normalized().dot(v.normal) < -0.2:
        # 凹陷（负高度标记）
        peaks.append((vi, -height, v.co, v.normal))
```

### 5. 半径衰减 Laplacian 平滑

```python
smooth_radius = 0.003  # 3mm
smooth_zone = {}
for vi, h, co, n in peaks:
    for v in bm.verts:
        d = (v.co - co).length
        if d < smooth_radius:
            w = 1.0 - (d / smooth_radius) ** 2  # 中心权重最大
            smooth_zone[v.index] = max(smooth_zone.get(v.index, 0), w)

# 迭代平滑
for it in range(8):
    for vi, w in smooth_zone.items():
        v = bm.verts[vi]
        neighbors = [e.other_vert(v) for e in v.link_edges]
        avg = sum(n.co for n in neighbors) / len(neighbors)
        v.co = v.co.lerp(avg, 0.6 * w)  # strength=0.6
```

### 6. 凹陷填充

```python
for vi, h, co, n in peaks:
    if h < 0:  # 凹陷
        v = bm.verts[vi]
        lift = -h * 0.8  # 抬升 80% 深度
        v.co += n * lift
```

## 关键陷阱

### cavity 渲染伪影

开启 cavity 时，下眼睑的"黑色小点"看起来像是几何缺陷。
关闭 cavity 后大部分消失——是**微起伏在 cavity 着色下的阴影**，非真实几何。

**验证方法**：渲染时关闭 `scene.display.shading.show_cavity`，
对比同一视角的 cavity 开/关图像。

### vision 分辨率极限

1200×900 分辨率下，vision 无法可靠区分：
- 真实几何颗粒（>0.2mm）
- 正常解剖纹理（<0.2mm 微起伏）
- 睫毛线凹槽阴影

**结论**：网格层面 peaks=0 时，vision 报告的"颗粒"多为伪影或正常解剖结构，
不应继续平滑（会损失卧蚕细节）。

### background 模式无 sculpt brush

`bpy.ops.sculpt.brush_stroke` 需要 3D 视口上下文，background 模式**不可用**。
替代方案：半径衰减 Laplacian（smooth brush 的数学等价）。

## 迭代记录 (2026-07-23)

| 轮次 | 操作 | peaks | 平滑顶点 | 结果 |
|------|------|-------|----------|------|
| 1 | 半径衰减平滑 (5mm 候选区) | 199 | 2127 | 尖锐凸起消除 |
| 2 | 全局微平滑 (peaks=0) | 0 | 55 | 表面均匀化 |
| 3 | 全局微平滑 (peaks=0) | 0 | 15 | 收敛 |
| 4 | 扩大候选区 8mm + 凹陷填充 | 249+13 | 2883+13 | 睑缘颗粒消除 |

## 性能

- 反投影：12/13 成功（1 MISS 因遮挡）
- 检测+平滑：~10 秒（96 万顶点模型）
- 迭代 4 轮总时间：~2 分钟