# Body Wrap 失败分析 (2026-07-29)

## 结论
所有自动 wrap 方法在 AI 生成高模（含衣服）上彻底失败，已放弃。

## 根因

### 1. 衣服嵌套 (致命)
AI 高模（Tripo）结构：外层衣服表面 → 衣服内表面 → 身体表面（三层嵌套）。
所有"最近点"算法找到衣服内表面而非身体表面。

### 2. 法线反转 (53.1%)
AI 生成网格 53.1% 面法线朝内。`make_consistent(inside=False)` 修复无效，
因为衣服嵌套是结构性问题，法线修复不解决嵌套。

### 3. MetaHuman Body 多连通分量
Body 有 14 个连通分量（躯干、左右手臂各3段、左右脚等）。
Head 只有 1 个。分组件 Shrinkwrap 同样失败（每组件仍投影到衣服内表面）。

## 已尝试方法 (全部失败)

| 方法 | 结果 | 数据 |
|------|------|------|
| Shrinkwrap NEAREST | 压扁 | X span 1.809→0.979m |
| Shrinkwrap 修复法线后 | 压扁 | 同上 |
| PROJECT | 穿不透 | 平均距离 507mm, 7.5% 成功 |
| Surface Deform | 几乎无效 | 0.3% 顶点成功 |
| RBF (骨骼landmark) | 膨胀 | Y span→1.324m, 距离 610mm |
| Affine (仿射) | 扭曲 | 混入旋转 |
| Scale+Translate | 仅BBox对齐 | 不贴合表面，失去wrap意义 |
| Decimate+Shrinkwrap | 压扁 | 降面不改变嵌套结构 |
| 分组件Shrinkwrap | 全部塌缩 | 分量0: X→1/6, 分量1-2: X→一条线 |

## Head vs Body 关键差异

| 维度 | 头部 (v3.4 成功) | 身体 (全部失败) |
|------|-----------------|----------------|
| 连通分量 | 1个 | 14个 |
| 衣服干扰 | 无 | 有（嵌套） |
| 锚点数量 | 478个 | ~20个 |
| 锚点密度 | 极高 | 极低 |
| 初始投影距离 | <1mm | 50-600mm |

## 理论可行方向 (未验证)
- 剥离衣服 → 裸体高模 → Shrinkwrap（但宽松衣物下可能无身体几何）
- Deformation Transfer (Sumner 2004) — 需要 dense correspondence
- Non-Rigid ICP (pytorch-nicp) — 同样受衣服干扰
- 不做 wrap，QR 后 Data Transfer UV（身体部分从 MetaHuman 传，衣服部分自动UV）
