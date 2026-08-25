# RBF Landmark 全身变形工作流 — 已废弃 (2026-07-28)

## ⚠️ 结论：RBF 方案不可行

**用户确认：RBF 变形结果"完全不对"。** vision 分析也确认模型"极度肥胖/宽大体态"。

### 根因分析

1. **非 landmark 区域膨胀**：TPS 和高斯 RBF 在控制点稀疏区域（如躯干中间）会产生"鼓起"效应。16 个 landmark 太稀疏——躯干只有 6 个点，躯干侧面/肋骨/腰部没有控制点；手臂只有 3 个点，上臂/前臂中段没有控制点。
2. **RBF 只做变形不做包裹**：landmark 位置精确匹配（<30mm），但 landmark 之间自由插值导致膨胀。
3. **sigma 调参无效**：测试了 sigma=0.3/0.5/0.7/1.0 倍平均间距，躯干中心位移都在 0.05-0.06m，差别不大。膨胀是 RBF 数学特性，不是参数问题。

### 核心矛盾

| 方法 | 做什么 | 不做什么 | 失败模式 |
|------|--------|----------|----------|
| Shrinkwrap | 包裹（贴到表面） | 变形（不纠正姿势） | 姿势不同就崩 |
| RBF (TPS/高斯) | 变形（landmark 驱动） | 包裹（不贴表面） | 控制点稀疏时膨胀 |

**行业标准（R3DS Wrap/Faceform Wrap）是分两步**：先变形（含姿势校正），再法线方向投影包裹。且有嘴唇/眼睑检测器处理薄壁结构。

### 不要再做的事

- ❌ 不要用 16 个 landmark 的 RBF 做全身变形——控制点太稀疏，必然膨胀
- ❌ 不要调 sigma 参数——对膨胀无显著影响
- ❌ 不要用 TPS 或高斯 RBF——两者结果类似，都膨胀

## 历史记录

### 16 个标准 Landmark

| 编号 | 名称 | 编号 | 名称 |
|------|------|------|------|
| 01 | 头顶 head_top | 09 | 左腕 wrist_L |
| 02 | 下巴 chin | 10 | 右肩 shoulder_R |
| 03 | 胸口 chest | 11 | 右肘 elbow_R |
| 04 | 腹部 abdomen | 12 | 右腕 wrist_R |
| 05 | 后背 back | 13 | 左膝 knee_L |
| 06 | 骨盆 pelvis | 14 | 左踝 ankle_L |
| 07 | 左肩 shoulder_L | 15 | 右膝 knee_R |
| 08 | 左肘 elbow_L | 16 | 右踝 ankle_R |

### Landmark 精度（变形后）

| 部位 | 平均误差 | 最大误差 |
|------|---------|---------|
| 头/躯干 | ~5mm | 9mm |
| 肩 | ~5mm | 5mm |
| 肘 | ~26mm | 27mm |
| 腕 | ~12mm | 13mm |
| 膝/踝 | ~17mm | 22mm |

所有 landmark 误差 < 30mm——landmark 位置精确匹配，但非 landmark 区域膨胀。

### 变形后 bbox 对比

| | X span | Y span | Z span |
|---|---|---|---|
| MetaHuman (A-pose) | 1.16m | 0.42m | 1.80m |
| Tripo (T-pose) | 1.81m | 0.31m | 1.80m |
| RBF v1 (TPS) | 1.64m | 0.30m | 1.77m |
| RBF v2 (高斯) | 1.63m | 0.31m | 1.76m |

X span 不足（1.63 vs 1.81），手臂展开程度略不足。

### 废弃文件

- `wrapped_rbf_v1.blend`（TPS）— 废弃
- `wrapped_rbf_v2.blend`（高斯）— 废弃
- `landmark_check.txt`（landmark 精度检查）— 保留作参考

## 替代方案调研结果 (2026-07-28 完成)

详见 `references/topology-transfer-methods.md` — 完整方法对比和开源实现清单。

### ✅ 已确认最佳方案：ARAP + Surface Deform 混合流程

1. **ARAP 变形**：As-Rigid-As-Possible，保持局部刚性，**不膨胀**（直接解决RBF核心问题）
   - 开源：`libigl/libigl-python-bindings` (369★), `oobma/ARAP-deformer` (2★, Blender专用)
   - Blender内置 Laplacian Deform Modifier 类似但需骨架
2. **Surface Deform**：Blender内置，ARAP变形后低模与高模同姿态时绑定贴合
3. **增加控制点**：16→50+，沿关节链和躯干网格加密

### 其他可行方案
- **Deformation Transfer (Sumner 2004)**：`mickare/Deformation-Transfer-for-Triangle-Meshes` (213★, MIT)
  - 数学上最严格，自动扩展稀疏marker到密集对应
  - 需先做A-pose→T-pose变形（可用ARAP）
- **Non-Rigid ICP**：`wuhaozhe/pytorch-nicp` (275★, GPU加速)
  - 自动加密控制点，但需迭代求解

### RBF膨胀的6种解决方案（已调研）
1. 增加控制点密度（16→50-100）
2. Wendland紧支撑核替代TPS（`scipy RBFInterpolator(kernel='wendland')`）
3. 正则化项（体积保持+拉普拉斯平滑约束）
4. **RBF+ARAP混合**（推荐：RBF粗对齐→ARAP刚性修正）
5. 分区域RBF（参考 `yamahigashi/MayaMeshRetarget`）
6. 用Non-Rigid ICP替代纯RBF

### 行业标准流程（多步骤组合）
```
增加控制点(16→50+) → RBF/Wendland粗对齐 → ARAP局部刚性修正(消除膨胀) → Surface Deform精细贴合 → 手动修正衣服区域
```
**核心原则**：先解决姿势(ARAP)，再解决表面贴合(Surface Deform)。不要试图一步到位（Shrinkwrap失败，RBF膨胀）。
