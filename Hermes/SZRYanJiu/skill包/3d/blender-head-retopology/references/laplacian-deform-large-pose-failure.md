# Laplacian Deform 在大幅度姿势变形中的失败 (2026-07-28)

## 问题

Blender 内置 `LAPLACIANDEFORM` 修改器在 A-pose→T-pose 变形中产生严重畸变：
- **尖顶**：头顶被向上拉伸成锥形
- **躯干膨胀**：腹部臃肿、肥胖
- **手腕折弯**：前臂到手腕处剧烈向下折角
- **脚部拉伸**：脚部被拉长成扁平薄片

## 根因

1. **Hook 空对象约束太强**：16 个 landmark 对全身 Laplacian 变形太少，Hook 把顶点强行拉到目标位置，导致局部撕裂
2. **局部坐标保持失败**：Laplacian 变形保持局部微分坐标，但大幅度变形时（手臂旋转 90°），局部坐标无法保持，导致整体失真
3. **躯干中间无约束**：16 个 landmark 中躯干只有 6 个点，躯干侧面/肋骨/腰部没有控制点，自由插值导致膨胀

## 与 ARAP 的对比

| 方法 | 原理 | 优点 | 缺点 | 结果 |
|------|------|------|------|------|
| Laplacian Deform | 保持局部微分坐标 | 简单，Blender 内置 | 大幅度变形失真 | ❌ 严重畸变 |
| ARAP | 保持局部刚性变换 | 不膨胀，保持形状 | 需要连通网格 | ❌ 网格不连通失败 |
| RBF | 径向基函数插值 | landmark 精确 | 控制点稀疏时膨胀 | ⚠️ 躯干膨胀 |

## 不要做的事

- ❌ 不要用 Laplacian Deform 做 A-pose→T-pose 变形
- ❌ 不要用 Hook 空对象做全身约束（16 个点太少）
- ❌ 不要期望 Laplacian Deform 能保持局部形状在大变形下

## 适用场景

Laplacian Deform 适合：
- 小幅调整（如修复自相交、微调顶点位置）
- 局部变形（如面部表情微调）
- 有骨架/控制点密集的场景

不适合：
- 大幅度姿势变形（A-pose→T-pose）
- 全身变形（控制点稀疏）
- 无骨架/控制点稀疏的场景

## 替代方案

1. **分区域变形**：躯干刚性，四肢独立，交界处混合
2. **骨骼驱动**：加骨骼，旋转到目标姿势
3. **ARAP+Surface Deform**：ARAP 变形+Surface Deform 贴合
4. **RBF+增加控制点**：16→50+ 控制点

## 参考

- Blender Laplacian Deform 文档：https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/laplacian_deform.html
- ARAP 失败分析：见 `arap-metahuman-body-failure.md`
- RBF 膨胀分析：见 `rbf-full-body-deformation.md`
