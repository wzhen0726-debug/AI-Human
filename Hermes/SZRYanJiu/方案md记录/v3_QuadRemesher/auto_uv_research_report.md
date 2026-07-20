# Blender全自动UV展开方案调研报告

> 场景：全自动化数字人管线，20-25万面低模，不能手动操作，非AAA级质量标准。

## 一、Smart UV Project 在人体模型上的实际质量

### 算法原理
Smart UV Project 基于面的法线方向将模型分割为多个投影组，对每组沿最优角度做平面投影→展开→缝合。核心参数 `angle_limit`（默认66°）控制分组阈值：角度越低=更多分组=更少拉伸但更多岛。

### 实际质量评估（20-25万面人体模型）

| 维度 | 表现 | 严重程度 |
|------|------|----------|
| **接缝位置** | 不可控，可能出现在面部、胸部等关键区域。算法自动在尖锐角度处切割，面部鼻子/耳朵周围必然出现接缝 | ⚠️ 高 |
| **岛碎片化** | 严重。人体曲面复杂，会产生大量碎片岛（50-200+岛），尤其手指、耳朵、面部细节区域 | ⚠️ 高 |
| **拉伸** | 可通过调低 `angle_limit` 缓解，但代价是更多碎片。默认设置下高曲率区域（耳朵、鼻子）有明显拉伸 | ⚠️ 中 |
| **对称性** | 无保证。左右两侧UV布局可能不同，对需要对称纹理的角色模型是致命的 | 🔴 致命 |
| **UV空间利用率** | 碎片化导致利用率低，大量间隙浪费 | ⚠️ 中 |

### 结论
**Smart UV Project 单独使用不适合人体模型**，即使用于非AAA级管线。核心问题不是"画面不够好"而是"接缝位置不可控"和"无对称性"——这会导致纹理绘制和烘焙出现根本性问题。

---

## 二、自动标记接缝算法

### 现有方案：基于边缘角度自动检测→标记→Unwrap

Blender 5.1 提供了完整的 API 支持：

```python
# 1. 基于角度自动选边
bpy.ops.mesh.edges_select_sharp(sharpness=0.523599)  # 30° 阈值

# 2. 标记为接缝
bpy.ops.mesh.mark_seam(clear=False)

# 3. 使用标准Unwrap（非Smart UV Project）
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
```

`bpy.ops.mesh.set_sharpness_by_angle(angle, extend)` 可在 Blender 5.1 中基于角度设置锐边，然后可转换为接缝。

### 更精细的算法思路

```
对每条边计算二面角(dihedral angle) → 超过阈值(如60°)标记为候选接缝
→ 过滤短边链(孤立边不标记) → 确保接缝形成闭合环
→ 在对称轴上额外标记接缝(保证左右UV对称) → 执行Unwrap
```

这种方法在社区中常被称为 "auto seam from hard edges" 或 "edge angle based seam"，但**没有现成的Blender内置一键方案**——需要自己写Python脚本。

---

## 三、其他自动UV方案

### 3.1 UVPackmaster（推荐度：⭐⭐⭐⭐）

| 维度 | 详情 |
|------|------|
| 类型 | Blender插件，付费（$29-49） |
| 核心能力 | GPU加速UV打包，不是UV展开工具 |
| 自动化 | **Python SDK可嵌入**，支持脚本化操作 |
| 免费SDK | 提供免费SDK用于开发 |
| 打包算法 | 业界最高效，支持CUDA/Vulkan GPU加速 |
| 其他功能 | UV对齐/堆叠算法、辅助工具 |
| 局限 | **不负责接缝标记和展开**，只负责打包已有UV岛 |

### 3.2 RizomUV（推荐度：⭐⭐⭐）

| 维度 | 详情 |
|------|------|
| 类型 | 独立软件，专业级UV展开 |
| 价格 | 约$300-1500/年 |
| CLI/自动化 | 有Lua脚本API，但**无明确的headless CLI模式** |
| Blender集成 | 需要导出OBJ/FBX→RizomUV处理→导回 |
| 展UV质量 | 业界顶级，自动展开远优于Smart UV Project |
| 管线集成难度 | 中等。需额外安装软件，通过子进程调用 |

### 3.3 Magic-UV（推荐度：⭐⭐⭐⭐）

| 维度 | 详情 |
|------|------|
| 类型 | Blender内置插件（Release级） |
| 价格 | 免费 |
| 功能 | UV复制/粘贴、翻转/旋转、镜像、对齐、打包等 |
| 自动化 | 所有功能可通过`bpy.ops.uv.*`调用 |
| 局限 | **不包含自动接缝标记或展开**，是UV编辑辅助工具 |

### 3.4 Blender内置 Unwrap（推荐度：⭐⭐⭐⭐⭐）

| 维度 | 详情 |
|------|------|
| 方法 | `ANGLE_BASED`（默认）、`CONFORMAL`、`MINIMUM_STRETCH` |
| 质量 | Angle Based 对有机模型效果良好，远优于 Smart UV Project |
| 前提 | **需要已有接缝标记** |
| 自动化 | 配合自动接缝检测可完全自动化 |

---

## 四、后处理改善Smart UV结果

### 4.1 自动打包
`bpy.ops.uv.pack_islands()` 支持：
- `rotate=True` — 旋转岛以优化布局
- `scale=True` — 缩放岛填充UV空间
- `margin=0.001` — 岛间间距
- `shape_method='CONCAVE'` — 精确形状(凹形)匹配

### 4.2 缝合小岛
**没有自动缝合小岛的API。** `bpy.ops.uv.stitch()` 需要手动选择边，不可自动化。小岛问题只能从源头解决——改进接缝策略减少碎片。

### 4.3 自动旋转/缩放
`pack_islands` 已包含旋转和缩放功能。`bpy.ops.uv.average_islands_scale()` 可均衡岛缩放。

### 结论
后处理能改善布局效率，但**不能解决接缝位置错误和碎片化问题**。如果Smart UV Project产生了面部接缝，后处理无法修复。

---

## 五、推荐方案：全自动UV管线

### 方案A：纯Blender（推荐 ⭐⭐⭐⭐⭐）

```
1. 基于边缘角度自动标记接缝
   bpy.ops.mesh.edges_select_sharp(sharpness=30°)
   bpy.ops.mesh.mark_seam()

2. 补充对称轴接缝（关键！）
   - 沿X=0平面对称轴标记接缝
   - 确保左右UV对称

3. 标准Unwrap
   bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)

4. 后处理
   bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.005)
   bpy.ops.uv.average_islands_scale()
```

**优点**：完全免费，零依赖，100%自动化，对称性可控
**缺点**：质量取决于接缝自动检测的阈值调优

### 方案B：Blender + UVPackmaster（推荐 ⭐⭐⭐⭐）

在方案A基础上，将步骤4替换为UVPackmaster的打包：
- 更高的UV空间利用率
- GPU加速（200K面模型约快5-10x）
- 成本：$29-49一次性

### 方案C：Blender → RizomUV → Blender（推荐 ⭐⭐⭐）

在方案A的步骤1-2后，导出OBJ到RizomUV展开→导回。
- 质量最高，但管线复杂度高
- 需要安装额外软件
- 成本：$300+/年

---

## 六、明确结论

**自动化+可接受质量：可行。** 但必须满足以下条件：

1. **不能使用Smart UV Project** — 接缝不可控，无对称性，不适合人体
2. **必须使用基于边缘角度的自动接缝标记 + 标准Unwrap**
3. **必须沿对称轴（X=0）标记接缝** — 保证左右UV对称
4. **后处理用pack_islands优化布局**

推荐方案：**纯Blender方案A**（基于边缘角度自动标记接缝 + Angle Based Unwrap + pack_islands），零成本、全自动、可接受质量。

如果对UV空间利用率要求高，可在此基础上叠加UVPackmaster（方案B）。