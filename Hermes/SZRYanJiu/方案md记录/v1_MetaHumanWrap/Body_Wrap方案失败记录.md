# MetaHuman Body Wrap 方案失败记录

> **状态**: ❌ 已放弃（2026-07-29）  
> **目的**: 将 MetaHuman 标准低模（含完整拓扑+UV）包裹到 Tripo AI 高模表面，以继承 UV  
> **结论**: 所有自动 wrap 方法均因 Tripo 高模的**衣服嵌套**和**法线反转**问题而彻底失败

---

## 一、方案初衷

### 1.1 为什么要做 wrap

Tripo AI 高模经过 QuadRemesher 降面后，UV 展开质量极差（均匀 quad 网格导致 1000+ 碎岛，所有自动 UV 方案评分 ≤ 4.5/10）。

MetaHuman 低模自带完整拓扑和标准 UV（Body 32K面 / Head 60K面，U 1.01-1.99 第二通道），如果能 wrap 到高模上，就能直接继承 UV，绕过 QR 的 UV 问题。

### 1.2 参考的成功案例

**v3.4 头部 wrap 方案**（fit_v3.py）数值指标达标但**视觉质量不可用**：
- 方法：MediaPipe 478 面部特征点 → Procrustes 对齐 → Shrinkwrap 4轮 → 锚定迭代 25轮（Laplacian 平滑）
- 数值：0.402mm 均值误差，96.2% < 1mm
- **实际问题**：耳朵偏小、上唇扭曲、内眼角拉伸、鼻翼错位、颈部锯齿，视觉质量差，不可用于生产

---

## 二、实验环境与数据

### 2.1 源模型

| 模型 | 来源 | 面数 | 姿势 | 特征 |
|------|------|------|------|------|
| MetaHuman Body | Epic MetaHuman | ~32K面 | A-pose（原始）→ T-pose（Mixamo绑定后） | 14个连通分量，裸体，含标准UV |
| MetaHuman Head | Epic MetaHuman | ~60K面 | 同Body | 单一连通分量 |
| Tripo 高模 | Tripo AI → 修复后 | 193万面 | T-pose | 含衣服嵌套，53.1%面法线反转 |

### 2.2 T-pose MetaHuman 制作流程

```
原始A-pose FBX → Mixamo绑定 → 制作T-pose动画 → 导出T-pose FBX
→ Blender导入 → 修复armature scale(×100) → frame_set(2)
→ modifier_apply("Armature") → 删除骨骼
→ 顶点级坐标变换(x*0.01, y=-z*0.01, z=y*0.01) → 居中
```

**结果**：T-pose MetaHuman，X span=1.91m，脸朝-Y

### 2.3 Tripo 高模几何缺陷

| 问题 | 严重程度 | 影响 |
|------|----------|------|
| **衣服嵌套** | 🔴 致命 | 外层衣服 + 内层身体，Shrinkwrap 找到衣服内表面 |
| **53.1% 面法线反转** | 🔴 致命 | 投影方向混乱，NEAREST 和 PROJECT 都失效 |
| **AI生成网格** | 🟡 中等 | 拓扑不均匀，但 QR 可以修复 |

---

## 三、已尝试方案及结果

### 3.1 Shrinkwrap (NEAREST_SURFACEPOINT) — 完整模型

| 项目 | 数据 |
|------|------|
| 输入 | T-pose MetaHuman (scale+translate对齐后) + Tripo 高模 |
| 方法 | `bpy.ops.object.modifier_apply("Shrinkwrap")` NEAREST_SURFACEPOINT |
| 结果 | ❌ X span 从 1.809m 压扁到 0.979m |
| 原因 | 衣服嵌套导致投影到衣服内表面 |

### 3.2 Shrinkwrap — 修复法线后

| 项目 | 数据 |
|------|------|
| 前置操作 | 对 Tripo 做 `bpy.ops.mesh.normals_make_consistent(inside=False)` |
| 结果 | ❌ 依然压扁，法线修复无效 |
| 原因 | 衣服嵌套是结构性问题，法线修复不解决嵌套 |

### 3.3 PROJECT 方法

| 项目 | 数据 |
|------|------|
| 方法 | `wrap_method = 'PROJECT'`，沿法线方向投影 |
| 结果 | ❌ 平均投影距离 507mm，仅 7.5% 顶点成功 |
| 原因 | 衣服表面与裸体表面距离太远，投影穿不透 |

### 3.4 Surface Deform

| 项目 | 数据 |
|------|------|
| 方法 | Surface Deform Modifier + Bind |
| 结果 | ❌ 仅 0.3% 顶点投影成功 |
| 原因 | Surface Deform 需要源和目标已大致贴合，且传递的是变形而非包裹 |

### 3.5 RBF (骨骼 landmark)

| 项目 | 数据 |
|------|------|
| landmark 来源 | Mixamo 骨骼 tail 位置（肩X≈0.190，肘X≈0.445，腕X≈0.720）|
| 核函数 | `scipy.interpolate.RBFInterpolator` linear 核 |
| 结果 | ❌ Y span 膨胀至 1.324m，平均距离 610mm |
| 原因 | 骨骼 landmark 太稀疏（~20个），RBF 在 landmark 之间不可控 |

### 3.6 仿射变换 (Affine)

| 项目 | 数据 |
|------|------|
| landmark 来源 | 同 RBF |
| 方法 | 最小二乘法求仿射矩阵 |
| 结果 | ❌ 混入旋转，模型变形扭曲 |
| 原因 | 仿射变换是全局的，不适合局部形变 |

### 3.7 纯缩放+平移 (Scale+Translate)

| 项目 | 数据 |
|------|------|
| 方法 | BBox 对齐：scale = trip_bbox_size / mh_bbox_size，translate = trip_center - mh_center |
| 结果 | ✅ BBox 完美匹配 Tripo |
| **问题** | ❌ **失去了 wrap 的意义**：MetaHuman 没有贴合到高模表面，只是整体对齐 |

### 3.8 Shrinkwrap — 简化 Tripo (Decimate) 后

| 项目 | 数据 |
|------|------|
| 前置操作 | Decimate 降面到 10万面 |
| 结果 | ❌ 依然压扁 |
| 原因 | 降面不改变衣服嵌套结构 |

### 3.9 分组件 Shrinkwrap（最后一轮尝试）

| 项目 | 数据 |
|------|------|
| 方法 | 把 MetaHuman 14 个连通分量拆成 14 个独立物体，分别 Shrinkwrap |
| 分量分析 | 分量0=躯干(1789v)，分量1-2=右手臂(5052v)，分量3=右脚(2003v)，分量4=左手臂远端(2789v)... |
| 结果 | ❌ 全部塌缩 |
| 详细数据 | 分量0: X[-0.24,0.22]→[-0.04,0.04]（塌缩到1/6）; 分量1-2: X[0.71,0.90]→[0.49,0.49]（塌缩到一条线）|
| 原因 | **衣服内表面**比身体表面更近，NEAREST 把每个分量的顶点拉到衣服夹层里 |

---

## 四、根因总结

### 4.1 核心矛盾：衣服嵌套

```
Tripo 高模结构（从外到内）：
  ┌─────────────────────┐
  │   外层衣服表面       │  ← Shrinkwrap 找到的
  │   ┌─────────────┐   │
  │   │ 衣服内表面   │   │  ← 也被找到
  │   │ ┌─────────┐ │   │
  │   │ │ 身体表面 │ │   │  ← 我们想投影到的
  │   │ │ ┌─────┐ │ │   │
  │   │ │ │骨骼  │ │ │   │
  │   │ │ └─────┘ │ │   │
  │   │ └─────────┘ │   │
  │   └─────────────┘   │
  └─────────────────────┘
```

所有基于"最近点"的算法（Shrinkwrap NEAREST、RBF、Surface Deform）都会找到衣服表面而非身体表面。

### 4.2 MetaHuman 连通分量问题

MetaHuman Body 有 **14 个连通分量**（躯干、左右手臂各3段、左右脚等），不是单一网格。
- v3.4 头部数值达标是因为头部是**单一连通分量**
- 身体多分量 + Shrinkwrap = 每个分量独立投影到错误位置

### 4.3 与 v3.4 头部的关键差异

| 维度 | 头部 (v3.4 数值达标但视觉差) | 身体 (全部失败) |
|------|-----------------|----------------|
| 连通分量 | 1个 | 14个 |
| 衣服干扰 | 无 | 有（衣服嵌套） |
| 锚点数量 | 478个（MediaPipe面部特征点） | ~20个（骨骼landmark） |
| 锚点密度 | 极高（面部全覆盖） | 极低（仅关节处） |
| 投影距离 | <1mm（初始化就贴合） | 50-600mm（衣服间隙） |

---

## 五、理论上可行的方向（未验证）

### 5.1 剥离 Tripo 衣服 → 裸体高模

如果能从 Tripo 高模中分离出身体部分（去掉衣服），然后 Shrinkwrap MetaHuman 到裸体高模，问题可能解决。

**难点**：
- 衣服和身体网格是连通的（不是独立物体），需要基于法线/曲率分析做分割
- 宽松衣物下方的身体几何可能缺失（AI 不生成看不到的部分）

### 5.2 Deformation Transfer (Sumner 2004)

学术黄金标准，用三角形变换传递变形而非直接包裹。有 Python 实现（`mickare/Deformation-Transfer-for-Triangle-Meshes`）。

**难点**：需要 dense correspondence，衣服遮挡下无法建立。

### 5.3 Non-Rigid ICP (NICP)

`pytorch-nicp` GPU 加速，逐步变形。

**难点**：同样受衣服干扰影响。

### 5.4 不做 wrap，QR 后手动处理 UV

放弃 wrap 思路，QR 降面后：
- 身体部分：用 Data Transfer 从 MetaHuman 传 UV（需要位置对齐）
- 衣服部分：用 QR 自动 UV（质量差但可能够用）

---

## 六、教训总结

1. **不要盲目套用头部方案到身体** — 头部无衣服 + 单分量 + 密集锚点，身体全不满足
2. **Shrinkwrap NEAREST 在有衣服嵌套时必死** — 与法线无关，是结构性问题
3. **scale+translate 对齐不是 wrap** — 只是 BBox 匹配，不贴合表面
4. **骨骼 landmark 太稀疏** — 20 个点做 RBF/Affine 控制不住中间区域
5. **AI 生成高模的几何质量不可控** — 法线反转 + 衣服嵌套是 AI 生成的固有缺陷
6. **wrap 的意义是贴合表面传递 UV，不是 BBox 对齐** — 用户明确纠正

---

## 七、产出文件

| 文件 | 说明 |
|------|------|
| `test02/output/wrap/wrapped_shrinkwrap_v1.blend` | Shrinkwrap 失败结果 |
| `test02/output/wrap/wrapped_surface_deform_v1.blend` | Surface Deform 失败结果 |
| `test02/output/wrap/wrapped_rbf_bone_v1.blend` | RBF 骨骼 landmark 失败结果 |
| `test02/output/wrap/wrapped_scale_repair_v1.blend` | 纯缩放+平移对齐（成功但无意义） |
| `test02/output/wrap/wrapped_split_sw_v1.blend` | 分组件 Shrinkwrap 失败结果 |

---

*文档创建: 2026-07-29 | 状态: 已归档，不再沿此路线继续*
