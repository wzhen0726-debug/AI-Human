# 仿射变换全身对齐 (Affine Full-Body Alignment)

> 2026-07-28 验证：最小二乘法仿射变换优于 RBF，无整体扭曲。

## 核心方法

**仿射变换**（缩放+旋转+平移）用最小二乘法求解，不做 RBF 非线性插值。

```python
# P: 源点 (MetaHuman landmark), Q: 目标点 (Tripo landmark)
P_ext = np.hstack([P, np.ones((len(P), 1))])  # N x 4
A, residuals, rank, sv = np.linalg.lstsq(P_ext, Q, rcond=None)

linear = A[:3, :]    # 3x3 旋转/缩放
translate = A[3, :]  # 1x3 平移

# 应用
deformed = verts @ linear + translate
```

## 为什么优于 RBF

| 方法 | X span | Y span | Z span | 扭曲 |
|------|--------|--------|--------|------|
| RBF gaussian | 2.083 | 0.882 | 2.366 | ❌ 严重膨胀 |
| RBF linear | 1.925 | 0.553 | 1.818 | ⚠️ 轻微扭曲 |
| **仿射** | **1.957** | **0.396** | **1.736** | ✅ **无扭曲** |

- **RBF 是全局插值**，16 个控制点之间自由变形 → 头椭圆、脚拉长、身体"肥胖"
- **仿射是全局线性变换**，所有顶点统一缩放+旋转+平移 → 保持体型比例

## 奇异值检查

仿射矩阵的奇异值应接近相等（均匀缩放）：

```python
U, S, Vt = np.linalg.svd(linear)
print(S)  # [1.29, 1.02, 0.95] — 接近 1，接近均匀缩放
```

如果奇异值差异大（如 [2.0, 0.5, 0.1]），说明有剪切/非均匀缩放，可能产生扭曲。

## Landmark 精度

15 个 landmark（去掉 back 异常点）精度 12-40mm，正常体型差异。

## 限制

- **只做整体对齐**，不做局部变形。手臂比 Tripo 长 10cm 的问题无法解决（仿射是均匀缩放）。
- 需要 **Shrinkwrap 或 Surface Deform 精修** 来贴合局部轮廓。
- 但 Shrinkwrap 会塌陷（最近点吸附），Surface Deform 需要姿势一致。

## 推荐流程

```
1. Mixamo 绑定 A-pose → 导出 T-pose 动画 → 应用骨骼 → T-pose 网格
2. 几何分析找 16 个 landmark
3. 仿射变换对齐到 Tripo（最小二乘法）
4. 检查奇异值（应接近均匀缩放）
5. 如需局部贴合，用 Surface Deform（姿势已一致）
```

## 文件

- `test02/output/wrap/wrapped_affine_v1.blend` — 仿射对齐结果
