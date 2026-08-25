# Voxel Remesh + Laplacian 调研结论（2026-07-23）

## 背景

用户要求调研"Voxel Remesh+Laplacian"这个流程的重要性，评估是否应该加回高模修复阶段。

## 结论：不加 Voxel Remesh，升级 Laplacian 为渐进式

### Voxel Remesh — 明确不加（与 v7 决策一致）

| 维度 | 评估 | 依据 |
|------|------|------|
| 面部细节 | ❌ 毁灭性损失 | v6 实测：0.003/0.004/0.005 三种 voxel size 均丢失 80-90% 面部细节（唇/鼻/眼窝糊化） |
| 拓扑质量 | ⚠️ QR 不需要 | Quad Remesher 自带 remeshing，不需要水密代理输入。27 非流形边+24 边界边在 QR 容忍范围内 |
| 黏连修复 | ⚠️ 无直接帮助 | 黏连修复用的是 KDTree 近距检测+法线推开，与网格是否水密无关 |
| 烘焙 | ❌ 反而有害 | 烘焙需要高模保留面部细节投射法线/AO。Voxel 降面后细节永久丢失，烘焙质量下降 |

**唯一不可替代的价值**：水密化。但当前修复后 27 非流形边+24 边界边对 QR 不构成障碍，
且面部细节是烘焙质量的生命线。**结论：高模修复阶段不加 Voxel Remesh。**

### Laplacian 平滑 — 应升级为渐进式（从头模管线移植）

**头模管线 A/B 测试结论**（blender-head-retopology skill, session 2026-07-08）：

| 方案 | 结果 | 判定 |
|------|------|------|
| 固定 0.5→0.15 | 面部细节被抹平 | ❌ 过激进 |
| **渐进 0.35→0.10** | 去噪+保细节平衡最佳 | ✅ 最优 |
| 固定 0.3（当前 v7） | 早期去噪不足，晚期可能过度 | ⚠️ 可改进 |

**渐进式核心逻辑**：
- 早期迭代：anchor 位移大，需要较强平滑（0.35）消除粗变形
- 晚期迭代：接近收敛，需要轻微平滑（0.10）保留已拟合的细节

**公式**：`smooth_f = 0.35 - 0.25 * (iteration / total_iterations)`

**当前 v7 repair.py 的问题**：`laplacian_smooth(obj, iterations=2, lambda_factor=0.3)`
固定 0.3，2 次迭代。对于 193 万面高模：
- 第 1 次 0.3 可能不足以消除 fill_holes 后的局部凸起
- 第 2 次 0.3 可能过度平滑面部微细节

**建议升级**：改为 3 次渐进迭代（0.35, 0.22, 0.10），或保持 2 次但改为（0.35, 0.10）。

## 用户决策（2026-07-23）

用户明确要求：
1. 优化算法提升算法，不是跳过或排除
2. 调研 Voxel Remesh+Laplacian 的重要性
3. 如果确实有较大作用就加上，并解释清楚

**交付结论**：Voxel Remesh 不加（理由如上表），Laplacian 升级为渐进式（从头模管线移植 0.35→0.10）。

## 相关文件

- 头模管线渐进式平滑细节：`blender-head-retopology` SKILL.md "Progressive Laplacian Smoothing" 章节
- v7 修复管线（当前生产版本）：`references/repair-pipeline-v7.md`
- v6 Voxel Remesh 失败记录：`references/repair-pipeline-v6.md`
