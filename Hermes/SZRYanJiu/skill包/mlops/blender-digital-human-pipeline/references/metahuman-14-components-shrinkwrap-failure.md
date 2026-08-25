# MetaHuman Body 14 连通分量与 Shrinkwrap 失败分析 (2026-07-29)

## 核心发现

MetaHuman 低模 Body **不是单个整体网格**，而是 **14 个分离的连通分量**：

| 分量 | 顶点数 | 描述 | X span |
|------|--------|------|--------|
| 0 | 1789 | 躯干 | 0.467m |
| 1-2 | 5052 | 右臂（两段） | 0.190m + 0.189m |
| 3 | 2003 | 右脚 | 0.119m |
| 4-5 | 5578 | 左臂（两段） | 0.585m + 0.477m |
| 6 | 3345 | 左臂远端 | 0.166m |
| 7-8 | 5052 | 右臂（两段） | 0.190m + 0.188m |
| 9 | 2003 | 右脚 | 0.119m |
| 10-11 | 6134 | 左臂（两段） | 0.594m + 0.163m |
| 12-13 | 2602 | 手指/脚趾 | 0.113m + 0.113m |

**总计**: 56,748 顶点（Body）+ 头部另计

## 为什么 Shrinkwrap 必然失败

### 方法 1: NEAREST_SURFACEPOINT（默认）
```python
mod.wrap_method = 'NEAREST_SURFACEPOINT'
```
**结果**: X span 从 1.809m 压扁到 0.979m（54% 缩小）

**原因**: Shrinkwrap 把每个连通分量独立投影到目标表面。手臂分量被拉到躯干中心（因为那里更近），脚分量被拉到地面，整体 X 跨度大幅收缩。

### 方法 2: PROJECT（沿法线投影）
```python
mod.wrap_method = 'PROJECT'
mod.use_project_x = True
mod.use_project_y = True
mod.use_project_z = True
mod.use_negative_direction = True
mod.use_positive_direction = True
```
**结果**: bbox 保持 1.809m（不压扁），但 **仅 7.5% 顶点真正投影到表面**

**验证**: BVHTree find_nearest 显示平均距离 507mm，中位数 648mm。90%+ 顶点找不到投影交点，位置未变。

**原因**: MetaHuman 法线方向和 Tripo 表面不匹配，射线找不到交点。

### 方法 3: Surface Deform（表面绑定）
```python
mod = mh_obj.modifiers.new(name="SurfaceDeform", type='SURFACE_DEFORM')
mod.target = tripo
mod.falloff = 14.0
bpy.ops.object.surfacedeform_bind(modifier=mod.name)
```
**结果**: bbox 保持 1.809m，但 **仅 0.3% 顶点真正投影到表面**

**验证**: 平均距离 491mm，中位数 637mm。Surface Deform 的绑定机制对多连通分量网格无效。

### 方法 4: 对每个分量独立投影
```python
for comp_idx, comp in enumerate(components):
    for v_idx in comp:
        v = mh_body.data.vertices[v_idx]
        world_co = mh_body.matrix_world @ v.co
        location, normal, face_idx, distance = bvhtree.find_nearest(world_co)
        if location is not None:
            offset = normal * 0.002
            target_world = location + offset
            target_local = mh_body.matrix_world.inverted() @ target_world
            v.co = target_local
```
**结果**: X span 从 1.809m 压扁到 0.981m（54% 缩小）

**验证**: 平均距离 289mm，57% 顶点 <5mm。

**原因**: 即使对每个分量独立处理，衣服覆盖区域的分量（手臂袖子内）找不到正确的最近表面——投影到衣服外壳而不是人体表面。

## 其他失败方法

### RBF thin_plate_spline（15 个 landmark）
```python
from scipy.interpolate import RBFInterpolator
rbf = RBFInterpolator(P, Q, kernel='thin_plate_spline', smoothing=0.01)
deformed = rbf(verts)
```
**结果**: Y span 从 0.313m 爆炸到 1.324m（423% 增大），整体扭曲

**原因**: 15 个控制点太稀疏，薄板样条在非控制点区域自由变形，导致头变椭圆、脚拉长。

### 仿射变换（最小二乘）
```python
A, _, _, _ = np.linalg.lstsq(P_ext, Q, rcond=None)
linear = A[:3, :]
translate = A[3, :]
deformed = verts @ linear + translate
```
**结果**: Y span 从 0.313m 爆炸到 1.402m（448% 增大）

**原因**: 最小二乘求解引入了轴混合（线性矩阵非对角元素太大），混入了旋转和剪切。

## 唯一成功方案：纯缩放+平移

```python
sx = tripo_xspan / mh_xspan  # 0.946
sy = tripo_yspan / mh_yspan  # 0.889
sz = tripo_zspan / mh_zspan  # 0.997

for v in obj.data.vertices:
    v.co.x = (v.co.x - mh_center.x) * sx + tripo_center.x
    v.co.y = (v.co.y - mh_center.y) * sy + tripo_center.y
    v.co.z = (v.co.z - mh_center.z) * sz + tripo_center.z
```

**结果**:
- bbox 完全匹配: X span=1.809, Y span=0.313, Z span=1.800
- UV 差异: 0.000000（182,448 个 UV 坐标完全保留）
- 无扭曲（纯缩放+平移，无旋转，无变形）

**文件**: `test02/output/wrap/wrapped_scale_repair_v1.blend`

## 为什么这是正确方案

### WRAP 的真正目的

用户明确纠正：**WRAP 是为了解决 UV 展开问题，不是追求表面完美贴合**。

- **QR（Quad Remesher）** 生成的均匀 quad 网格 UV 展开碎片化（1145-2000 个岛）
- **MetaHuman** 自带标准 UV（Body 32K/60K 面，U 1.01-1.99 第二通道）
- **包裹后继承 MetaHuman UV** 比追求表面贴合更重要

### 衣服干扰是次要问题

用户纠正：**衣服无所谓，QR 之后布线也一样乱**。

Tripo 高模有衣服（额外几何），MetaHuman 没有，拓扑差异太大。所有自动投影方法（Shrinkwrap、Surface Deform、RBF、仿射）都无法处理这种差异。但衣服区域不需要完美贴合——后续 QR 重拓扑后，衣服区域的 UV 可以从 MetaHuman 传递（Data Transfer modifier）。

## 关键教训

1. **MetaHuman Body 是 14 个连通分量** — 任何基于"最近点"的投影方法都会失败
2. **Shrinkwrap 对多连通分量网格无效** — 每个分量独立投影，导致结构崩溃
3. **Surface Deform 对多连通分量网格无效** — 绑定机制不支持分离部件
4. **RBF 需要密集控制点** — 15 个 landmark 太稀疏，导致全局扭曲
5. **仿射变换混入旋转** — 最小二乘求解引入轴混合，非对角元素过大
6. **纯缩放+平移是唯一可靠方案** — bbox 匹配 + UV 完全保留
7. **WRAP 的目的是 UV 继承** — 不是表面完美贴合，衣服区域可以粗略对齐

## 后续步骤

1. **纯缩放+平移** → `wrapped_scale_repair_v1.blend`（已完成）
2. **QR 重拓扑** → Tripo 高模降面到 50K-100K
3. **Data Transfer UV** → 从 MetaHuman 传 UV 到 QR 后的 Tripo
4. **烘焙** → Tripo 高模纹理烘焙到 QR 后的 Tripo（使用 MetaHuman UV）
5. **骨骼绑定** → Mixamo 或 Auto-Rig Pro

## 验证数据

### 纯缩放+平移结果
| 指标 | MetaHuman (缩放后) | Tripo | 匹配 |
|------|-------------------|-------|------|
| X span | 1.809m | 1.809m | 100% ✓ |
| Y span | 0.313m | 0.313m | 100% ✓ |
| Z span | 1.800m | 1.800m | 100% ✓ |
| UV 差异 | 0.000000 | - | 完全保留 ✓ |

### Shrinkwrap 失败对比
| 方法 | X span | 投影成功率 | 平均距离 |
|------|--------|-----------|----------|
| NEAREST_SURFACEPOINT | 0.979m (54%) | - | - |
| PROJECT | 1.809m | 7.5% | 507mm |
| Surface Deform | 1.809m | 0.3% | 491mm |
| 分量独立投影 | 0.981m (54%) | 57% <5mm | 289mm |

## 参考文件

- `test02/output/wrap/wrapped_scale_repair_v1.blend` — 纯缩放+平移结果（UV 完全保留）
- `test02/output/wrap/mh_tpose_final.blend` — MetaHuman T-pose（站立，脸朝 -Y）
- `test02/bone_landmarks.json` — 18 个骨骼 landmark（从 Mixamo FBX 提取）
