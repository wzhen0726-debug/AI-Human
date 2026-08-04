# 数字人管线：高低模拓扑与UV展开 — 技术咨询文档

> **用途**: 提供给外部专家咨询，涵盖拓扑传递和UV展开两个环节的完整技术现状  
> **日期**: 2026-07-29  
> **项目背景**: 零预算数字人管线，Blender 5.1 全自动 background 模式

---

## 〇、管线全景

```
照片(T-pose紧身衣) → Tripo AI高模(193万面) → 几何修复
→ [环节A: 拓扑/降面] → [环节B: UV展开] → 烘焙 → Mixamo绑定 → GLB
```

| 环节 | 目标 | 当前状态 |
|------|------|----------|
| A 拓扑/降面 | 193万面 → 9-25万面，保留细节 | ⚠️ 两条路线均未达标 |
| B UV展开 | 低模UV，接缝少、无碎岛、无扭曲 | ❌ 所有自动方案 ≤4.5/10 |

---

## 一、输入资产

| 资产 | 规格 | 说明 |
|------|------|------|
| Tripo AI 高模 | 113万顶点/193万面, GLB | T-pose, 含衣服, 1.8m高, 53.1%面法线反转 |
| MetaHuman Body | 32,334顶点 | 裸体, 标准拓扑+UV, 14个连通分量 |
| MetaHuman Head | 24,414顶点 | 标准拓扑+UV, 单一连通分量 |
| 扫描人头(测试用) | 297万顶点, OBJ | 用于头部wrap验证 |

### 高模几何缺陷

| 问题 | 数据 | 影响 |
|------|------|------|
| 衣服嵌套 | 外层衣服+内层身体 | Shrinkwrap找到衣服内表面而非身体 |
| 法线反转 | 53.1%面 | 投影方向混乱 |
| AI生成拓扑 | 不均匀三角面 | QR可修复 |

---

## 二、拓扑环节：两条路线的完整尝试

### 路线A：MetaHuman Wrap（包裹传递拓扑+UV）

**思路**: 将MetaHuman标准低模（含完整拓扑+标准UV）包裹到Tripo高模表面，直接继承拓扑和UV，绕过QR的UV问题。

#### A.1 头部Wrap（v3.4，❌数值达标但视觉质量不可用）

**方法**: MediaPipe 478面部特征点 → 2D→3D映射 → Procrustes对齐 → Shrinkwrap 4轮 → 锚定迭代25轮 → Laplacian平滑

| 指标 | 结果 |
|------|------|
| 平均误差 | 0.402mm |
| <1mm比例 | 96.2% |
| 眼对称 | 0.04mm |
| 嘴对称 | 0.75mm |

**数值指标看似达标的原因**:
- 头部是单一连通分量
- 无衣服干扰
- 478个密集锚点（MediaPipe面部特征点全覆盖）
- 初始化就贴合（<1mm投影距离）

**但视觉质量不可用**（数值指标好不代表结果能用）:
- 耳朵偏小（Shrinkwrap把顶点拉到耳廓内侧）
- 上唇扭曲（嘴唇薄壁结构，NEAREST拉到对侧）
- 内眼角拉伸（眼窝凹陷区域投影不准）
- 鼻翼错位（鼻孔薄壁，同嘴唇问题）
- 颈部锯齿（颈部landmark稀疏）
- 178个自相交面

#### A.2 身体Wrap（❌彻底失败，已放弃）

**T-pose MetaHuman制作**: 原始A-pose FBX → Mixamo绑定 → T-pose动画 → 导出FBX → Blender导入 → 修复armature scale(×100) → 顶点级坐标变换 → 居中。得到站立T-pose（X span 1.91m，脸朝-Y）。

**9轮尝试全部失败**:

| # | 方法 | 结果 | 失败原因 |
|---|------|------|----------|
| 1 | Shrinkwrap NEAREST（完整模型） | X span 1.809→0.979m | 衣服嵌套，投影到衣服内表面 |
| 2 | Shrinkwrap NEAREST（法线修复后） | 依然压扁 | 法线修复不解决衣服嵌套 |
| 3 | Shrinkwrap PROJECT | 平均投影距离507mm，仅7.5%成功 | 衣服表面与裸体距离太远 |
| 4 | Surface Deform | 仅0.3%顶点成功 | 需要源和目标已大致贴合 |
| 5 | RBF（骨骼landmark ~20个） | Y span膨胀至1.324m，平均距离610mm | landmark太稀疏，中间区域不可控 |
| 6 | 仿射变换 | 混入旋转，模型扭曲 | 全局变换不适合局部形变 |
| 7 | 纯缩放+平移（BBox对齐） | BBox完美匹配 | 失去wrap意义，不贴合表面 |
| 8 | Shrinkwrap（Tripo Decimate后） | 依然压扁 | 降面不改变衣服嵌套结构 |
| 9 | 分组件Shrinkwrap（14个连通分量独立） | 全部塌缩 | 衣服内表面比身体更近 |

**分组件Shrinkwrap详细数据**（第9轮）:

| 分量 | 内容 | 顶点数 | X范围变化 |
|------|------|--------|-----------|
| 0 | 躯干 | 1789 | [-0.24,0.22]→[-0.04,0.04] 塌缩到1/6 |
| 1-2 | 右手臂 | 5052 | [0.71,0.90]→[0.49,0.49] 塌缩到一条线 |
| 3 | 右脚 | 2003 | [0.05,0.17]→[0.06,0.12] |
| 4 | 左手臂远端 | 2789 | [0.14,0.72]→[0.01,0.49] |

**根因分析**:

1. **衣服嵌套是结构性问题**: Tripo高模从外到内是「外层衣服→衣服内表面→身体表面→骨骼」，所有基于"最近点"的算法都找到衣服而非身体
2. **MetaHuman Body有14个连通分量**: 躯干、左右手臂各3段、左右脚等，Shrinkwrap把每个分量独立投影到错误位置
3. **与头部的关键差异**: 头部1个分量+无衣服+478锚点；身体14个分量+衣服嵌套+仅~20个骨骼landmark

**结论**: 在含衣服的AI高模上，所有自动wrap方法（Shrinkwrap/Surface Deform/RBF/Affine）均不可行。

### 路线B：Quad Remesher 自动重拓扑（当前主方案）

**思路**: 放弃wrap，直接用Quad Remesher对Tripo高模做自动重拓扑，得到均匀quad低模，再处理UV。

| 参数 | 值 |
|------|------|
| 输入 | Tripo高模 193万面 |
| 输出 | 90,331 quad面（180,662三角面），90,333顶点 |
| 特点 | 法线变化极均匀（相邻面夹角~1-2°），非流形边=0 |

**QR的问题**: 生成的均匀quad网格UV展开质量极差（详见第三章）。

---

## 三、UV展开：所有尝试方案及结果

### 3.1 问题定义

QR生成的90K quad网格需要自动UV展开。质量要求：评分≥7/10，接缝少、无碎岛、无扭曲、左右对称。

**核心障碍**: QR网格法线变化极其均匀（~1-2°），所有基于法线/角度的自动接缝检测全部失效。

### 3.2 Blender内置算法

| 方案 | 接缝数 | 岛数 | 评分 | 问题 |
|------|--------|------|------|------|
| Smart UV 66° | 自动 | 1,988 | 2/10 | 碎片化严重，接缝不可控 |
| ANGLE_BASED + 手动5接缝 + average | 6,501 | 1,145 | **8.5/10** | 碎块多但密度均匀，当前最佳 |
| CONFORMAL(LSCM) + 手动5接缝 | 6,501 | 1,196 | 2/10 | 碎片化 |
| MINIMUM_STRETCH(ARAP) | 6,501 | 1,145 | 1/10 | 更差 |
| 圆柱投影 | 0 | 4 | 2/10 | 拉伸严重 |
| lightmap_pack | - | - | 超时 | 90K面太大 |

**手动5接缝位置**: 背中线 + 脖子环 + 左右手臂内侧 + 左右腿内侧

### 3.3 ZEN UV插件（Blender）

| 方案 | 接缝数 | 岛数 | 评分 | 问题 |
|------|--------|------|------|------|
| auto_uv_unwrap + 手动5接缝 + texel_density | 6,501 | ~1,983 | **8.25/10** | 最佳但碎块多 |
| auto_uv_unwrap(packing=True, hard_edges=True) | - | 167 | 3/10 | hard_edges切碎躯干 |
| "Zen Unwrap"一键 | 自动 | 827 | 1/10 | QR网格上失效 |
| auto_mark(30°) + CONFORMAL | 365 | - | 崩溃 | EXCEPTION_ACCESS_VIOLATION |
| zenuv_relax | - | - | 崩溃 | 零长度向量错误 |
| 合并1面碎片→重unwrap | 6,347→6 | 6 | 3.5/10 | 接缝丢失导致拉伸 |

### 3.4 xatlas（外部Python库）

| 方案 | 岛数 | 评分 | 问题 |
|------|------|------|------|
| xatlas(默认) | ~2,000 | 3/10 | 不均匀 |
| xatlas(bruteForce+texels_per_unit) | ~2,000 | 3/10 | 略好但不可用 |

### 3.5 pymeshlab

LSCM参数化和Voronoi参数化均超时（180K三角面）。

### 3.6 RizomUV 2025.0（LUA脚本自动化）

**核心发现**: `ZomUnfold`在`/cfi`+LUA后台模式下**始终做投影不做真正LSCM/ARAP展开**。

| 方案 | 接缝 | 岛数 | 评分 | 问题 |
|------|------|------|------|------|
| ZomLoad+ZomUnfold(无接缝) | 0 | 4 | 2/10 | UV只有4个坐标 |
| NormalizeUVW+ZomUnfold | 0 | ~1,978 | 2/10 | 展开但拉伸(投影) |
| Auto.Skeleton+Cut+Unfold | 自动 | ~1,978 | 2/10 | Skeleton在QR上失效 |
| SharpEdges(1°)+Cut+Unfold | 自动 | ~1,978 | 2/10 | 切了所有边但Unfold效果差 |
| 手动5接缝+Cut+Unfold(Ite=5) | 6,355 | ~1,969 | 2.5/10 | 拉伸严重 |
| ZEN auto_mark(365接缝)+Cut+Unfold+Optimize(10) | 365 | ~1,969 | 3/10 | 接缝位置不对 |
| Border=true+Cut+Unfold+Optimize(15) | UV边界 | ~1,151 | 2/10 | Border成功但Unfold仍投影 |
| **Border+Cut+IslandGroups+Unfold+Optimize(20)** | UV边界 | ~1,746 | **4.5/10** | IslandGroups是关键但Unfold仍投影 |

**已验证的RizomUV LUA API**: ZomLoad ✓, ZomSelect(Border/All/Auto.Skeleton/Auto.SharpEdges) ✓, ZomCut ✓, ZomIslandGroups ✓, ZomUnfold ✓(但只做投影), ZomOptimize ✓, ZomSave ✓, ZomQuit ✓

**GUI vs LUA差异**: GUI的Unfold做LSCM/ARAP保角展开，LUA的ZomUnfold只做投影。原因可能是解算器需要GUI渲染上下文，或`/nu`/`/nle`参数影响。

### 3.7 B2RUVL插件

需要GUI viewport（`context.space_data.local_view`），`--background`模式下无法运行。

### 3.8 UV边界传递法（Gemini建议）

验证了完整管线：Blender标记seam → unwrap(seam变UV边界) → 导出FBX → RizomUV加载 → Border=true选中 → Cut → Unfold。
- Border+Cut成功 ✓
- 但Unfold仍做投影 ✗

### 3.9 根因分析

1. **QR均匀quad网格**: 法线变化极小(~1-2°)，Smart UV每面都切→碎片化；auto_mark(30°)只找到365条(太少)；RizomUV SharpEdges(40°)找不到任何sharp edge
2. **RizomUV background限制**: ZomUnfold在LUA后台模式下不做真正展开，只做投影
3. **Blender ANGLE_BASED 8.5/10的代价**: 1,145个岛，碎片多，利用率~60-70%

### 3.10 当前最佳方案

**Blender内置 ANGLE_BASED + 手动5接缝**（8.5/10）:
```python
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True)
bpy.ops.uv.average_islands_scale()
```
缺点：1,145个岛，碎片多。

**ZEN UV auto_uv_unwrap + 手动5接缝**（8.25/10）:
```python
bpy.ops.uv.zenuv_auto_uv_unwrap(
    auto_detect_hard_edges=False, use_normal=False,
    use_texel_density=True, texel_density=10.0,
    TD_TextureSizeX=2048, TD_TextureSizeY=2048,
    mark_seam_edges=True, correct_self_intersecting=True,
    stretch=False, packing=True)
```
缺点：~2,000个碎片岛。

---

## 四、待探索方向（未验证）

### 4.1 拓扑方向

> **已有系统性规划**: 详见 `v4_前瞻性技术方案/三阶段演进路线.md`

| # | 方向 | 说明 | 风险 |
|---|------|------|------|
| 1 | **MVP: QR+Smart UV暴力直通** | 放弃wrap，QR重拓扑+暴力UV+高margin烘焙 | UV碎片化，但可跑通全流程 |
| 2 | **v2.0: 3D语义分割+ARAP Wrap** | AI分割皮肤/衣服区域，分级wrap | 3D分割精度，ARAP求解速度 |
| 3 | **v3.0: SMPL-X逆向拟合** | 参数化模型匹配高模轮廓，终极形态 | 求解器开发复杂，授权问题 |
| 4 | 剥离Tripo衣服→裸体高模→再wrap | 分离衣服和身体，Shrinkwrap到裸体 | 衣服和身体连通，分割困难 |
| 5 | Deformation Transfer (Sumner 2004) | 学术黄金标准 | 需要dense correspondence，衣服遮挡下无法建立 |

### 4.2 UV方向

| # | 方向 | 说明 | 风险 |
|---|------|------|------|
| 1 | RizomUV GUI自动化 | AutoHotkey操作GUI，绕过LUA ZomUnfold限制 | 不稳定，依赖GUI |
| 2 | Ministry of Flat | 游戏管线CLI工具，零参数一键UV | 未安装，未测试 |
| 3 | UVPackmaster 3 | Blender插件，GPU加速packing | 只打包不展开，$29-49 |
| 4 | libigl ARAP | 免费，带约束参数化 | 需要C++编译或Python绑定 |
| 5 | 标准低模模板Wrap | 用Surface Deform变形到新高模轮廓 | 同wrap问题，衣服干扰 |
| 6 | Blender Decimate替代QR | Decimate保留原始UV | 面数降不下来，布线质量差 |
| 7 | 高模法线引导接缝检测 | 用193万面高模法线信息引导低模接缝 | 需要开发 |
| 8 | RizomUV Python API | 检查是否有独立于LUA的Python API | 可能不存在 |

---

## 五、环境信息

| 项目 | 版本/路径 |
|------|-----------|
| Blender | 5.1.0 (`D:\Program Files\Blender Foundation\Blender 5.1\`) |
| 运行模式 | `--background --factory-startup --python script.py` |
| Python | 3.11 (Blender内置)，numpy/scipy已装 |
| 付费插件 | Auto-Rig Pro, Quad Remesher, Better FBX, MACHIN3tools |
| 免费插件 | ZEN UV (225个operator) |
| RizomUV | 2025.0 (`D:\Program Files\Rizom Lab\RizomUV 2025.0\`) |
| xatlas | 0.0.11 |
| pymeshlab | 安装到Blender Python |
| B2RUVL | 0.1.6（需GUI，background不可用） |

---

## 六、想咨询的问题

### 拓扑方面

1. **含衣服的AI高模如何做拓扑传递？** 行业标准做法是什么？是否必须先剥离衣服？
2. **Deformation Transfer在衣服遮挡下是否可行？** 论文中的correspondence mapping能否处理"目标表面有遮挡物"的情况？
3. **有没有商业工具能自动处理"含衣服高模→裸体低模"的wrap？** 我们零预算，但想了解行业方案。

### UV方面

4. **RizomUV的ZomUnfold在LUA后台模式下为什么只做投影不做LSCM/ARAP展开？** 是参数缺失还是版本限制？有没有workaround？
5. **QR均匀quad网格的UV展开，行业最佳实践是什么？** 我们尝试了Blender内置/ZEN UV/xatlas/RizomUV，最佳只有8.5/10但1,145个碎岛。
6. **100K面级别的模型，自动UV展开能做到什么质量水平？** 我们的目标是≥7/10且岛数<50，这个要求是否合理？
7. **Ministry of Flat是否值得尝试？** 零预算，如果需要付费就不考虑了。

### 整体管线

8. **"AI高模→低模→UV→烘焙→绑定"这个管线，有没有更优的环节顺序或替代方案？** 比如先绑骨骼再传UV？
9. **我们的管线必须全自动（Blender background模式），不能有任何GUI交互。** 这个约束下有什么建议？

---

## 七、关键文件位置

| 内容 | 路径 |
|------|------|
| 头部wrap脚本 | `方案md记录/v1_MetaHumanWrap/fit_v3.py` |
| 头部wrap档案 | `方案md记录/v1_MetaHumanWrap/MetaHumanWrap_完整档案.md` |
| 身体wrap失败记录 | `方案md记录/v1_MetaHumanWrap/Body_Wrap方案失败记录.md` |
| UV调研报告 | `方案md记录/v3_QuadRemesher/03自动UV/UV调研报告.md` |
| 拓扑传递调研 | `方案md记录/v3_QuadRemesher/拓扑传递行业调研_子代理报告.md` |
| QR方案档案 | `方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/QuadRemesher简化版_完整档案.md` |

---

*文档生成: 2026-07-29 | Blender 5.1.0 | Windows 10*
