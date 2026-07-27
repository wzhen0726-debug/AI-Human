# UV展开问题最终调研报告

## 一、项目背景

数字人角色管线：AI高模(Tripo, 193万面) → QuadRemesher低模(9万面quad) → UV展开 → 烘焙 → Mixamo骨骼绑定 → GLB/OBJ输出。

**核心问题**：QuadRemesher生成的均匀quad网格，UV展开质量极差，所有自动方案均无法达到可用水平(目标7/10以上)。

## 二、网格特征

- **面数**：90,331 quad面（180,662三角面）
- **顶点数**：90,333
- **拓扑**：QuadRemesher生成的均匀四边面网格
- **非流形边**：0（网格完全连续）
- **关键特征**：法线变化极其均匀，所有相邻面之间的法线夹角几乎相同（~1-2°）

## 三、已尝试方案及结果

### 3.1 Blender内置算法

| 方案 | 接缝 | 岛数 | 评分 | 问题 |
|------|------|------|------|------|
| Smart UV 66° | 自动 | 1988 | 2/10 | 碎片化 |
| ANGLE_BASED+average+手动5接缝 | 6501 | 1145 | 8.5/10 | 碎块多但密度均匀 |
| CONFORMAL(LSCM)+手动5接缝 | 6501 | 1196 | 2/10 | 碎片化 |
| MINIMUM_STRETCH(ARAP) | 6501 | 1145 | 1/10 | 更差 |
| 圆柱投影 | 0 | 4 | 2/10 | 拉伸严重 |
| lightmap_pack | - | - | 超时 | 90K面太大 |

### 3.2 ZEN UV插件

| 方案 | 接缝 | 岛数 | 评分 | 问题 |
|------|------|------|------|------|
| auto_uv_unwrap+手动5接缝+texel_density | 6501 | ~1983 | 8.25/10 | 最佳但碎块多 |
| auto_uv_unwrap(packing=True,hard_edges=True) | - | 167 | 3/10 | hard_edges切碎躯干 |
| proxy_zenunwrap_all_selected("Zen Unwrap"一键) | 自动 | 827 | 1/10 | QR网格上失效 |
| auto_mark(30°)+zenuv_unwrap(CONFORMAL) | 365 | - | 崩溃 | EXCEPTION_ACCESS_VIOLATION |
| zenuv_relax | - | - | 崩溃 | 零长度向量错误 |
| 合并1面碎片→重unwrap | 6347→6 | 6 | 3.5/10 | 接缝丢失导致拉伸 |

### 3.3 xatlas（外部Python库）

| 方案 | 岛数 | 评分 | 问题 |
|------|------|------|------|
| xatlas(默认) | ~2000 | 3/10 | 不均匀 |
| xatlas(bruteForce+texels_per_unit) | ~2000 | 3/10 | 略好但不可用 |

### 3.4 pymeshlab

LSCM参数化和Voronoi参数化均超时（180K三角面）。

### 3.5 RizomUV 2025.0（LUA脚本自动化）

**核心限制**：`ZomUnfold`在`--background`模式(通过`/cfi`+LUA调用)下**始终做投影不做真正LSCM/ARAP展开**。无论用什么参数(Border/IDs/Auto.Skeleton/NormalizeUVW)，ZomUnfold的输出都是正视图投影或圆形投影。

| 方案 | 接缝 | 岛数 | 评分 | 问题 |
|------|------|------|------|------|
| ZomLoad+ZomUnfold(无接缝) | 0 | 4 | 2/10 | UV只有4个坐标 |
| NormalizeUVW+ZomUnfold | 0 | ~1978 | 2/10 | 展开了但拉伸(投影) |
| NormalizeUVW+Auto.Skeleton+Cut+Unfold | 自动 | ~1978 | 2/10 | Skeleton在QR上失效 |
| NormalizeUVW+SharpEdges(1°)+Cut+Unfold | 自动 | ~1978 | 2/10 | 切了所有边但Unfold效果差 |
| 手动5接缝(edge IDs)+Cut+Unfold(Ite=5) | 6355 | ~1969 | 2.5/10 | 拉伸严重 |
| ZEN auto_mark(365接缝)+Cut+Unfold+Optimize(10) | 365 | ~1969 | 3/10 | 接缝位置不对 |
| Border=true+Cut+Unfold+Optimize(15) | UV边界 | ~1151 | 2/10 | Border机制成功但Unfold仍做投影 |
| **Border+Cut+IslandGroups(CreateFromCuts)+Unfold+Optimize(20)** | UV边界 | ~1746 | 4.5/10 | **IslandGroups是关键但Unfold仍投影** |
| ZEN auto_uv_unwrap→FBX→Border+Cut+IslandGroups+Unfold | UV边界 | ~1151 | 2/10 | 同上 |

**RizomUV LUA API验证：**
- `ZomLoad({File={Path=...,XYZUVW=true,UVWProps=true}})` ✓
- `ZomLoad({File={Path=...,XYZ=true},NormalizeUVW=true})` ✓ 重置UV
- `ZomSelect({PrimType="Edge",Border=true,ResetBefore=true})` ✓ 选中UV边界
- `ZomSelect({All=true})` ✓ 全选
- `ZomSelect({Auto={Skeleton=true}})` ✓ 执行但QR上无效
- `ZomSelect({Auto={SharpEdges={AngleMin=40}}})` ✓ 执行但QR上无效
- `ZomCut({PrimType="Edge",WorkingSet="Selected"})` ✓
- `ZomIslandGroups({Mode="CreateFromCuts"})` ✓ 重建岛分割
- `ZomUnfold({PrimType="Polygon",WorkingSet="All"})` ✓ 执行但**只做投影不做真正展开**
- `ZomOptimize({Iterations=15})` ✓
- `ZomPack({RootGroup="RootGroup",WorkingSet="All"})` 卡死(90K面)
- `ZomSave({File={Path=...}})` ✓
- `ZomQuit()` ✓
- `ZomUVSet({Mode="Create"})` ✗ nil value
- `U3dSet({Path="Prefs.PackOptions.MapResolution"})` ✗ 变量不存在
- `zenuv_relax` ✗ 零长度向量崩溃

**关键结论：RizomUV的`ZomUnfold`在`/cfi`+LUA后台模式下与GUI里的Unfold行为不同。GUI里的Unfold会做LSCM/ARAP保角展开，但LUA脚本的ZomUnfold只做简单投影。这可能是RizomUV 2025.0的限制或LUA API参数不足。即使加了`ZomIslandGroups({Mode="CreateFromCuts"})`重建岛分割后Unfold仍然做投影。**

### 3.6 B2RUVL插件

需要GUI viewport（`context.space_data.local_view`），在`--background`模式下无法运行。

## 四、根因分析

### 4.1 QR均匀quad网格的特性

QuadRemesher生成的网格法线变化极小(~1-2°)，所有基于法线/角度的自动接缝检测全部失效：
- Blender Smart UV → 每面都切 → 碎片化
- ZEN UV auto_mark(30°) → 只找到365条(太少)
- RizomUV SharpEdges(40°) → 找不到任何sharp edge
- RizomUV Auto.Skeleton → 无法识别骨架

### 4.2 RizomUV background模式限制

RizomUV的LUA `ZomUnfold`在`/cfi`+`/nu`+`/nle`后台模式下不执行真正的LSCM/ARAP展开。无论用什么参数组合：
- `NormalizeUVW=true` + `ZomUnfold` → 投影
- `Border=true` + `Cut` + `ZomUnfold` → 投影
- `Border=true` + `Cut` + `ZomIslandGroups(CreateFromCuts)` + `ZomUnfold` → 投影
- `ZomOptimize({Iterations=20})` → 不改善投影问题

GUI里的Unfold和LUA API行为不同的原因可能是：
1. ZomUnfold的LSCM/ARAP解算器需要GUI渲染上下文
2. `/nu`(no_uvs)或`/nle`(no_license_exit)参数影响了解算行为
3. RizomUV 2025.0版本LUA API限制

### 4.3 UV边界传递机制验证

验证了Gemini建议的"UV边界传递法"：
- Blender标记seam → unwrap(seam变UV边界) → 导出FBX → RizomUV加载 → `ZomSelect({Border=true})` → `ZomCut` → `ZomUnfold`
- **Border=true+Cut成功**：正确选中UV边界并切割
- **但Unfold仍做投影**：RizomUV的ZomUnfold没有做LSCM/ARAP展开

## 五、已验证的最佳方案

### 5.1 Blender最佳(8.25/10)

```python
# 1. 手动5条接缝(背中线+脖子环+左右手臂内侧+左右腿内侧)
# 2. ZEN UV auto_uv_unwrap
bpy.ops.uv.zenuv_auto_uv_unwrap(
    auto_detect_hard_edges=False, use_normal=False,
    use_texel_density=True, texel_density=10.0,
    TD_TextureSizeX=2048, TD_TextureSizeY=2048,
    mark_seam_edges=True, correct_self_intersecting=True,
    stretch=False, packing=True)
# 3. average_islands_scale + normalize
```
**缺点**：~2000个碎片岛，利用率~60-70%

### 5.2 Blender内置最佳(8.5/10)

```python
# 1. 手动5条接缝(6501条边)
# 2. ANGLE_BASED unwrap
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True)
# 3. average_islands_scale
bpy.ops.uv.average_islands_scale()
```
**缺点**：1145个岛，碎片多

### 5.3 RizomUV LUA管线(可运行但质量差)

```lua
ZomLoad({File={Path="in.fbx", ImportGroups=true, XYZUVW=true, UVWProps=true}})
ZomSet({Path="Prefs.FileSuffix", Value=""})
ZomSelect({PrimType="Edge", Border=true, ResetBefore=true})
ZomCut({PrimType="Edge", WorkingSet="Selected"})
ZomIslandGroups({Mode="CreateFromCuts"})
ZomUnfold({PrimType="Polygon", WorkingSet="All"})
ZomOptimize({Iterations=20})
ZomSave({File={Path="out.fbx"}})
ZomQuit()
```
**运行方式**：`cd "D:\Program Files\Rizom Lab\RizomUV 2025.0" && rizomuv.exe /cfi script.lua /nu /nle`
**问题**：ZomUnfold只做投影不做真正展开(2-4.5/10)

## 六、待探索方向

1. **RizomUV GUI自动化**：用AutoHotkey/Python GUI自动化操作RizomUV GUI(不通过LUA)，绕过ZomUnfold的background限制
2. **Ministry of Flat**：专为游戏管线设计的CLI工具，零参数一键UV（未测试，未安装）
3. **UVPackmaster 3**：Blender插件，Python API做packing（未测试，未安装）
4. **libigl ARAP**：免费，C++编译或Python绑定，带约束参数化（未测试）
5. **标准低模模板Wrap**：建立标准UV低模，用Surface Deform变形到新高模轮廓（彻底绕过UV展开）
6. **Blender Decimate替代QR**：Decimate保留原始UV避开QR碎片化
7. **高模法线引导**：用193万面高模的法线信息引导低模接缝检测
8. **RizomUV Python API**：检查RizomUV是否提供Python API(独立于LUA)，可能绕过LUA限制

## 七、环境信息

- **Blender**: 5.1.0 (D:\Program Files\Blender Foundation\Blender 5.1\)
- **运行模式**: --background (无GUI)
- **QuadRemesher**: 已安装，target=100K
- **ZEN UV**: 已安装（225个operator）
- **RizomUV**: 2025.0 (D:\Program Files\Rizom Lab\RizomUV 2025.0\)
- **B2RUVL**: 0.1.6（需GUI）
- **xatlas**: 0.0.11
- **pymeshlab**: 安装到Blender Python

## 八、文件位置

- 低模：`v5_run/03_remesh.blend`
- UV展开：`v5_run/04_uv.blend`
- 烘焙：`v5_run/05_bake.blend`
- 绑定：`v5_run/06_rig.blend`
- 最终输出：`v5_run/final.glb` / `v5_run/final.obj`
- 脚本目录：`scripts/`（rig_mixamo.py, launcher.py, bake.py, uv_pipeline.py等）
- RizomUV LUA：`v5_run/_rizom_*.lua`

---

# 附录：早期方案调研（2026-07-15）

> 以下为早期调研报告，作为方案演变背景参考。最终结论以上文为准。

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