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
