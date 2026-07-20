# 高模→低模 头部拓扑自动化 调研报告

## 1. Wrap4D / Faceform Wrap 包裹机制

**产品定位**：Faceform Wrap（原 R3DS Wrap）是业界标准的扫描→拓扑包裹软件，Wrap4D 是其 4D 序列扩展版。

**核心机制**：
- **FacialWrapping 节点**：结合 BlendWrapping + **嘴唇/眼睑检测器**，专为减少手动清理设计
- 嘴唇和眼睑的轮廓线被**单独检测并特殊处理**，不会让顶点穿到对面
- 对口腔、眼窝等凹陷区域，Wrap 使用**基于法线方向的投影**，不是简单的最近点包裹
- 使用**节点式工作流**：LoadGeom(高模) → LoadGeom(低模/模板) → SelectPointPairs(打点) → Wrapping(包裹)

**和我们的差距**：
- 我们没有嘴唇/眼睑轮廓检测 → 我们的 MediaPipe 轮廓点只匹配了 8/20 外唇点
- 我们没有法线方向约束的投影 → 我们的 NEAREST 会把顶点拉到对侧表面
- Wrap 需要**手动打点**（SelectPointPairs），但支持自动检测辅助

**参考**：https://faceform.com → 付费软件，约 $500/年

---

## 2. AI 屏幕识别打点 — 可行性与差距

**当前做法**：MediaPipe 2D 检测 → 6 方向渲染 → 2D→3D 映射（raycast）

**核心问题**：
- 2D→3D 映射不可靠：raycast 可能命中错误表面（鼻梁透视、眼眶侧面）
- 眉毛/鼻翼的轮廓点 Y 范围异常（21-30mm），过滤后只保留 41/81 个有效点
- MediaPipe 只能检测正面，侧面/后脑点位只能靠几何估算

**优化方向**：
- 使用**多视角 MediaPipe**：渲染 6 个方向，每个方向独立检测，3D 三角定位取交集
- 使用**3D 面部特征点检测器**（如 FaceMesh 的 3D 版本，468 个 3D 点）
- 使用**MediaPipe 的 3D 模式**：Face Landmarker 的 `FACE_LANDMARKS` 模式可输出 3D 世界坐标

**可行性**：中等。能显著提升正面点位的精度，但侧面/后脑仍是盲区。

---

## 3. UE5 MetaHuman "Mesh to MetaHuman" — 方案分析

**工作机制**（Epic 官方，闭源）：
- 上传任意 3D 头部扫描/模型 → 自动匹配 MetaHuman 模板
- 使用**深度学习模型**（Epic 自训），输入扫描网格，输出变形后的 MetaHuman 拓扑
- 核心组件：
  - **面部特征点检测**：类似 MediaPipe 但更鲁棒，覆盖整个头部
  - **空间特征编码**：将 3D 扫描编码为隐空间特征
  - **模板变形**：基于学习到的形状先验（shape prior），将 MetaHuman 模板变形到目标形状
  - **自监督训练**：使用大量 3D 扫描数据训练，不需要手动标注

**是否开源**：**否**。MetaHuman 的 Mesh to MetaHuman 是完全闭源的，模型和训练数据都不公开。

**能否复刻**：
- 核心难点是**训练数据**：需要数千个高质量 3D 头部扫描，覆盖不同人种/年龄/性别
- 隐空间形状先验的训练需要大量计算资源
- **相关开源项目**：
  - **FLAME**（MPI-IS）：参数化头部模型，类似 SMPL 的身体模型
  - **DECA**（MPI-IS）：从单张图片重建 3D 头部 + FLAME 参数
  - **NPHM**（Neural Parametric Head Models）：神经隐式头部模型
  - **HRN**（Head Registration Network）：CT 到模板的配准

**付费替代方案**：
- **Reallusion Headshot 2.0**（$199）：图片/扫描→CC 角色，自动拓扑
- **Faceform Wrap**（$500/年）：手动辅助的扫描包裹
- **Metahuman Creator**（免费）：通过 UE5 使用，需手动调整面部特征
- **ZBrush + ZWrap**：手动雕刻+包裹，最灵活但最耗时

---

## 4. 成熟的高模→低模拓扑全流程

### 4.1 全自动方案

| 方案 | 价格 | 适用场景 | 口腔/眼窝 | 面部布线 |
|------|------|----------|-----------|----------|
| **UE5 Mesh to MetaHuman** | 免费 | 头部扫描 | ✅ 自动处理 | ✅ MetaHuman 标准 |
| **Reallusion Headshot 2.0** | $199 | 照片/扫描 | ✅ 自动 | ✅ CC 标准 |
| **Faceform Wrap 4D** | $500/年 | 批量扫描 | ✅ 嘴唇/眼睑检测 | ✅ 任意模板 |
| **Quad Remesher** | $69 | 任意网格 | ❌ 需手动 | ❌ 无预设 |
| **Instant Meshes** | 免费 | 任意网格 | ❌ 无 | ❌ 无面部流线 |

### 4.2 半自动方案（推荐）

**流程 A：MediaPipe 打点 + Wrap 包裹**
1. 在扫描上自动检测面部特征点（MediaPipe 3D 模式）
2. 在模板上手动标记对应点（已有 21 个点）
3. 用 Wrap 软件的 FacialWrapping 节点包裹
4. 手动修正口腔/眼窝/耳朵区域

**流程 B：MetaHuman 匹配 + 拓扑转移**
1. 将扫描导入 UE5，用 Mesh to MetaHuman 自动匹配
2. 导出 MetaHuman 头部（带标准拓扑）
3. 如果需要自己的拓扑，用 Wrap 将 MetaHuman 拓扑转移到你的模板

**流程 C：FLAME/DECA 参数化拟合**
1. 用 DECA 从扫描渲染图重建 FLAME 参数
2. 将 FLAME 参数应用到你的模板（需要模板和 FLAME 的顶点对应关系）
3. 用 Shrinkwrap 精修表面

### 4.3 关键发现

**Wrap4D 的 FacialWrapping 的核心优势**：
- 专门的**嘴唇检测器**（lip detector）和**眼睑检测器**（eyelid detector）
- 可以训练**个性化检测器**（personalized detector），针对特定人物的面部特征
- 跟踪标记（tracking markers）用于极端表情

这解释了为什么我们的 Shrinkwrap 方案在嘴唇/眼窝区域失败——我们没有专门的嘴唇/眼睑检测器来处理这些薄壁结构。

---

## 5. 推荐路线

**立即可用**：
1. **改用 MediaPipe 3D 模式**（输出 3D 世界坐标，跳过 2D→3D 映射）
2. **增加嘴唇/眼睑锚点密度**：手动在模板上标记更多嘴唇轮廓和眼睑轮廓的顶点
3. **在 MediaPipe 中启用面部网格**（Face Mesh），获取 468 个 3D 点的完整面部拓扑

**中期方案**（1-2 周）：
- 购买 **Faceform Wrap**（$500/年），使用 FacialWrapping 节点
- 或使用 **UE5 Mesh to MetaHuman**（免费），导出 MetaHuman 拓扑后再用 Wrap 转移到你的模板

**长期方案**（1-2 月）：
- 基于 FLAME/DECA 开发自有的参数化头部拟合系统
- 收集/购买训练数据，训练个性化的嘴唇/眼睑检测器