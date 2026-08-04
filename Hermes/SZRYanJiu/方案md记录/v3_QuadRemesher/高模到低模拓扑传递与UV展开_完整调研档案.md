# 高模→低模拓扑传递与UV展开 — 完整调研档案

> **⚠️ 状态更新 (2026-07-29)**: Wrap 方案已全部放弃。头部 v3.4 数值指标达标(0.402mm)但视觉质量差(耳朵/嘴唇/眼角扭曲)，不可用于生产。身体因衣服嵌套彻底失败。本文档作为历史调研档案保留。

> 本文档记录数字人项目中"AI高模→低模拓扑传递（wrap/retopology）+ UV展开"两个核心环节的所有方案、执行进度、遇到的问题和尝试过的解决办法。供外部调研参考。

---

## 一、项目背景

### 1.1 项目目标

照片 → AI生成高模 → **低模拓扑传递** → **UV展开** → 烘焙 → 骨骼绑定 → GLB输出

### 1.2 输入资产

| 资产 | 规格 | 说明 |
|------|------|------|
| Tripo AI高模 | 113万顶点/193万面, GLB | T-pose, 含衣服, 1.8m |
| 混元AI高模 | 类似规格 | A-pose, 含衣服 |
| MetaHuman低模 | Body 32334顶点 + Head 24414顶点 | A-pose, 无骨骼无顶点组, 纯网格, cm单位(matrix_basis自带0.01缩放) |

### 1.3 核心矛盾

| 矛盾 | 详情 |
|------|------|
| **姿势差异** | MetaHuman是A-pose(手臂下垂), Tripo是T-pose(手臂水平展开) |
| **衣服干扰** | Tripo高模含宽松衣服, 衣服下方无身体几何, Shrinkwrap被衣服表面吸引 |
| **控制点稀疏** | 全身只有16个landmark, 控制点之间区域插值不可靠 |
| **零预算** | 不能用R3DS Wrap($500/年), ZWrap, Faceform Wrap等付费工具 |
| **无骨骼** | MetaHuman低模没有骨骼和顶点组, 无法通过骨骼旋转到T-pose |
| **Blender background限制** | 部分工具(RizomUV, B2RUVL)在--background模式下行为异常 |

### 1.4 环境

- Blender 5.1.0 (`D:\Program Files\Blender Foundation\Blender 5.1\`)
- Python 3.11 (Blender内置), numpy/scipy已安装
- 付费插件: Auto-Rig Pro, Quad Remesher, Better FBX, MACHIN3tools
- 免费插件: ZEN UV
- 运行方式: `--background --factory-startup --python script.py`

---

## 二、方案总览

项目经历了三个大版本的方案迭代：

| 版本 | 方案名 | 核心思路 | 状态 |
|------|--------|----------|------|
| v1 | MetaHuman全身Wrap | MetaHuman模板包裹AI高模, 保留MetaHuman拓扑 | ❌ 未完成, 头部wrap有未解决问题 |
| v2 | 镜像对称 | ZBrush Smart ReSym的Blender复刻 | ❌ 匹配率天花板74.4% |
| v3 | QuadRemesher简化版 | QR重拓扑+自动UV+Mixamo绑定 | ⚠️ UV展开质量不达标 |

当前在 **v3方案** 的框架下, 同时回退研究 **v1方案的wrap可行性**。

### 2.1 方案v1: MetaHuman Wrap（test01头部 + test02身体）

**思路**: 用MetaHuman标准低模拓扑包裹AI高模, 继承MetaHuman拓扑(面部环形线+关节布线+ARKit 52面绑兼容)

#### v1.1 头部Wrap（test01）

**方法**: MediaPipe 478面部特征点 → 2D→3D映射 → Procrustes对齐 → Shrinkwrap 4轮 → 锚定迭代25轮 → Laplacian表面修正

**结果**: 数值0.402mm均值, 96.2%<1mm, 眼对称0.04mm, 嘴对称0.75mm。**但视觉质量不可用**（耳朵/嘴唇/眼角扭曲+178自相交）

**未解决问题**:
- 耳朵偏小（Shrinkwrap把耳朵顶点拉到耳廓内侧最近表面, 不是耳廓外侧）
- 上唇扭曲（嘴唇薄壁结构, NEAREST把顶点拉到对侧嘴唇）
- 内眼角拉伸（眼窝凹陷区域, 投影方向不准）
- 鼻翼错位（鼻孔薄壁, 同嘴唇问题）
- 颈部锯齿（颈部landmark稀疏, 插值不平滑）

**根因分析**:
1. Shrinkwrap NEAREST_SURFACEPOINT不看对应关系, 只找最近表面 → 薄壁结构(嘴唇/眼睑/耳廓)顶点被拉到对侧
2. Shrinkwrap PROJECT需要准确的投影方向, 但MediaPipe特征点在侧面/后脑不可靠
3. 控制点(landmark)稀疏区域, 锚定迭代+Laplacian平滑不能完全修正

**关键技术细节**:
- 坐标系差异Bug: 扫描Z[-134,+134]mm(几何中心), 模板Z[-89,+283]mm(脖子位置), 差149mm → 必须用特征点Procrustes对齐, 不能用质心
- No-Pullback Bug: 表面修正后直接`v.co = tgt`跳回锚点 → 464/8280顶点扭曲(眉/鼻/嘴) → 修复: 不用pullback, 只用Laplacian平滑
- SVD旋转对齐失败: 12个特征点太稀疏+共面, 旋转矩阵放大MediaPipe误差 → 13.6mm误差 → 规则: 只用平移+均匀缩放, 不要旋转
- Blender单位是米不是毫米: 阈值0.5mm应写0.0005
- NumPy 2.0 pitfall: `ndarray.ptp()`移除, 用`np.ptp(arr)`
- BVH ray_cast API: 只接受位置参数, 不支持关键字
- 版本历史: v3.4-laplacian(数值0.402mm/96.2%/178自相交，但视觉质量差不可用)

**对比行业标杆(Faceform Wrap/R3DS Wrap)**:
- Wrap有**嘴唇检测器**和**眼睑检测器**, 专门处理薄壁结构
- Wrap用**基于法线方向的投影**, 不是简单最近点
- Wrap支持**节点式工作流**: LoadGeom → SelectPointPairs → Wrapping
- 付费$500/年, 我们零预算无法使用

#### v1.2 身体Wrap（test02）

**状态**: ❌ 所有方法均失败, 身体wrap未实现

**尝试过的所有方法**:

##### 方法A: 直接Shrinkwrap（v3, script 34_wrap_v3.py）

**做法**: MetaHuman Body缩放到1.8m → 绕Z-90°旋转 → 直接Shrinkwrap(NEAREST_SURFACEPOINT)到Tripo

**结果**: X span 0.26m（Tripo是1.81m）, 模型崩溃

**根因**: MetaHuman是A-pose(X span=0.52m, 手臂在Y方向), Tripo是T-pose(X span=1.81m, 手臂在X方向)。Shrinkwrap NEAREST把手臂顶点拉到最近的Tripo表面, 但最近表面是躯干衣服(距离近), 不是T-pose手臂末端(距离远)。

##### 方法B: 先旋转手臂再Shrinkwrap（v4-v5, script 36_wrap_v4.py, 37_wrap_v5_arms.py）

**做法**:
1. 识别手臂顶点(距离肩膀<0.6m且|Y|>0.12)
2. 绕肩膀点旋转手臂到T-pose(绕Z轴-90°)
3. 第一轮Shrinkwrap只影响躯干(顶点组限制)
4. 第二轮Shrinkwrap全身

**结果**: X span 0.94m, 模型变形

**根因**:
1. 距离阈值0.6m太小, 手的顶点(距离肩膀0.64m)没被捕获 → 手没旋转, 手臂折断
2. 把阈值改到0.8m后, 吞了太多躯干顶点(9448 vs 正常6053)
3. 第二轮全身Shrinkwrap又把旋转后的手臂拉回躯干衣服表面
4. **结论: Shrinkwrap在含衣服的高模上结构性失败, 无论是否先旋转手臂**

##### 方法C: 顶点组限制Shrinkwrap只影响躯干（v5, script 37_wrap_v5_arms.py）

**做法**: 创建"Torso"顶点组, Shrinkwrap只影响躯干顶点(权重1), 手臂顶点权重0

**结果**: 躯干Y span从1.4骤降到0.31, 被压扁

**根因**: Shrinkwrap NEAREST_SURFACEPOINT把所有顶点吸附到最近表面, Tripo在Y方向(前后厚度)很薄(0.31m), MetaHuman躯干被拉向最近表面导致压扁

##### 方法D: RBF变形 - TPS薄板样条（wrapped_rbf_v1.blend）

**做法**:
1. 用户在Tripo高模上标16个landmark(T-pose)
2. 用户在MetaHuman上标对应16个landmark(A-pose)
3. 用TPS(Thin Plate Spline)核函数计算RBF权重
4. 应用变形到MetaHuman网格

**landmark对应精度**: 所有16个点误差<30mm, 头/躯干<10mm

**结果**: T-pose姿势正确(手臂水平展开✓), 但vision分析报告"极度肥胖/宽大体态"

**根因**: TPS核函数在控制点稀疏时, 中间区域会"鼓起"。16个landmark中躯干只有6个点(胸/腹/背/骨盆), 躯干侧面/肋骨/腰部没有控制点, 自由插值导致膨胀。

##### 方法E: RBF变形 - 高斯核（wrapped_rbf_v2.blend）

**做法**: 同方法D, 但用高斯核`exp(-r²/2σ²)`替代TPS核`r²log(r)`, σ=0.359(控制点平均间距*0.5)

**结果**: bbox类似(X span 1.625 vs TPS的1.638), 同样有膨胀问题

**根因**: 不同核函数对躯干中心位移影响不大(0.05-0.06m), 说明膨胀主要是由landmark驱动的, 不是核函数性质。但landmark之间的区域仍会自由插值。

##### 方法F: 锚点迭代平滑（script 12_wrap_with_anchors.py）

**做法**: 在已有wrap结果上, 用landmark做锚点, 15轮迭代(锚点保持+非锚点Laplacian平滑), 再做Shrinkwrap

**结果**: 未实际验证(依赖已有wrap结果, 而wrap结果本身有问题)

**局限**: 仍然在最后一步用Shrinkwrap, 同样会崩

##### 方法G: 估算特征点对齐（script 33_align_v2.py）

**做法**: 用标准人体比例估算MetaHuman上的landmark位置(如肩在(-0.20, 0, mh_max_z*0.83))

**结果**: 估算位置不准, 手臂特征点用了T-pose位置(X方向展开), 但MetaHuman是A-pose(手臂在Y方向)

**根因**: 标准比例估算误差大, 不能替代实际几何分析或手动标记

#### v1.2 身体Wrap - 用户驱动的landmark标记工作流

**做法**: 创建blend文件包含MetaHuman模型+16个预命名空对象, 用户在Blender GUI中移动空对象到正确位置

**实施细节**:
- 空对象show_in_front=True(始终显示在最前面, 不被模型遮挡)
- 空对象用SPHERE类型, radius=0.015, 红色
- 模型hide_select=True(不可选中, 防止误移动)
- Tripo参考模型默认隐藏(hide_set=True), 避免混淆
- 16个landmark预填位置基于MetaHuman实际几何分析(不是标准比例估算)

**已完成的landmark文件**:
- `landmark_scene_v6.blend`: Tripo高模上的16个landmark(用户标记)
- `landmark_scene_mh_v2.blend`: MetaHuman上的16个landmark(用户标记)

**landmark列表**:
1. 头顶 2. 下巴 3. 胸口 4. 腹部 5. 后背 6. 骨盆
7. 左肩 8. 左肘 9. 左腕 10. 右肩 11. 右肘 12. 右腕
13. 左膝 14. 左踝 15. 右膝 16. 右踝

**landmark间距分析(MetaHuman A-pose → Tripo T-pose)**:
| 部位 | 距离 | 说明 |
|------|------|------|
| 头/躯干 | 60-100mm | 基本一致, 主要是Y方向(前后)偏移 |
| 肩 | ~57mm | 基本一致 |
| 肘 | ~256mm | A-pose下垂vs T-pose水平 |
| 腕 | ~453mm | 差异最大, 手臂要大幅拉伸 |
| 膝/踝 | ~55mm | 基本一致 |

#### v1.2 身体Wrap - 遇到的Bug汇总

1. **重复缩放Bug**: MetaHuman matrix_basis自带0.01缩放(cm→m), 脚本又手动`v.co *= 0.01`, 导致顶点坐标崩溃 → 修复: 直接transform_apply, 不手动缩放
2. **坐标系旋转Bug**: MetaHuman原始就是脸朝-Y, 和Tripo一致, 不需要旋转。但早期脚本错误地绕Z-90°旋转, 导致脸朝-X
3. **Blender 5.1 rotation_euler失效**: 设置rotation_euler后matrix_world不更新 → 必须用matrix_basis直接旋转
4. **Blender 5.1 Matrix.Rotation方向**: 与数学约定相反, 但实测一致(非memory记录的反向)
5. **Tripo GLB坐标系旋转**: 三步旋转(X-90° + Z-90° + Y-90°), 两步版本导致模型横躺
6. **空对象镜像失败**: Blender Ctrl+M对空对象位置无效(只镜像物体原点变换), 需要脚本读取位置取反X坐标

---

## 三、方案v3: QuadRemesher简化版

### 3.1 整体流程

```
AI高模(193万面) → 几何修复 → 黏连修复 → QuadRemesher(9万面quad) → UV展开 → 烘焙 → Mixamo绑定 → GLB
```

### 3.2 各阶段完成度

| 阶段 | 状态 | 完成度 | 说明 |
|------|------|--------|------|
| M1 高模修复 | ✅ 完成 | 100% | repair.py, 193万面保留, 法线修复, QA通过 |
| M2 黏连检测 | ✅ 完成 | 100% | adhesion.py, KDTree近距面对 |
| M3 QuadRemesher | ✅ 完成 | 100% | 9万面quad, 四边面 |
| M4 UV展开 | ❌ 未达标 | 40% | 最佳8.5/10但碎块多, 所有自动方案都有问题 |
| M5 烘焙 | ⚠️ 部分 | 60% | 可运行但衣服干扰未解决 |
| M6 绑定 | ✅ 完成 | 100% | Mixamo 20骨骼 |
| M7 GLB导出 | ✅ 完成 | 100% | final.glb输出 |
| M8 管线集成 | ⚠️ 部分 | 50% | launcher.py可跑通, 但UV质量不达标 |

### 3.3 UV展开详细调研（核心卡点）

#### 网格特征

- 面数: 90,331 quad面(180,662三角面)
- 顶点: 90,333
- 拓扑: QuadRemesher生成的均匀四边面网格
- 非流形边: 0
- **关键特征**: 法线变化极其均匀(~1-2°), 所有基于法线/角度的自动接缝检测全部失效

#### 已尝试方案及结果

| 方案 | 接缝 | 岛数 | 评分 | 问题 |
|------|------|------|------|------|
| Blender Smart UV 66° | 自动 | 1988 | 2/10 | 碎片化 |
| Blender ANGLE_BASED+手动5接缝 | 6501 | 1145 | 8.5/10 | 碎块多但密度均匀 |
| Blender CONFORMAL(LSCM)+手动5接缝 | 6501 | 1196 | 2/10 | 碎片化 |
| Blender MINIMUM_STRETCH(ARAP) | 6501 | 1145 | 1/10 | 更差 |
| Blender 圆柱投影 | 0 | 4 | 2/10 | 拉伸严重 |
| Blender lightmap_pack | - | - | 超时 | 90K面太大 |
| ZEN UV auto_uv_unwrap+手动5接缝 | 6501 | ~1983 | 8.25/10 | 最佳但碎块多 |
| ZEN UV auto_uv_unwrap(hard_edges) | - | 167 | 3/10 | hard_edges切碎躯干 |
| ZEN UV Zen Unwrap一键 | 自动 | 827 | 1/10 | QR网格上失效 |
| ZEN UV auto_mark(30°)+CONFORMAL | 365 | - | 崩溃 | EXCEPTION_ACCESS_VIOLATION |
| xatlas(默认) | ~2000 | ~2000 | 3/10 | 不均匀 |
| xatlas(bruteForce) | ~2000 | ~2000 | 3/10 | 略好但不可用 |
| pymeshlab LSCM | - | - | 超时 | 180K三角面太大 |
| RizomUV ZomUnfold(各种参数组合) | 变化 | ~1978 | 2-4.5/10 | **ZomUnfold在background模式只做投影不做真正展开** |

#### RizomUV background模式限制（关键发现）

RizomUV的`ZomUnfold`在`/cfi`+LUA后台模式下与GUI里的Unfold行为不同:
- GUI里的Unfold做LSCM/ARAP保角展开
- LUA脚本的ZomUnfold**只做简单投影**
- 无论用什么参数组合(NormalizeUVW/Border/Cut/IslandGroups/SharpEdges/Auto.Skeleton), Unfold都是投影

可能原因:
1. ZomUnfold的LSCM/ARAP解算器需要GUI渲染上下文
2. `/nu`(no_uvs)或`/nle`(no_license_exit)参数影响解算行为
3. RizomUV 2025.0版本LUA API限制

#### UV展开根因分析

**QR均匀quad网格的特性导致所有自动接缝检测失效**:
- QuadRemesher生成的网格法线变化极小(~1-2°)
- 基于法线/角度的自动接缝检测(Blender Smart UV, ZEN UV auto_mark, RizomUV SharpEdges, RizomUV Auto.Skeleton)全部失效
- 唯一有效的是**手动标记接缝**, 但手动5接缝产生1145-1983个碎片岛

#### UV展开已验证的最佳方案

**Blender内置最佳(8.5/10)**:
```python
# 1. 手动5条接缝(背中线+脖子环+左右手臂内侧+左右腿内侧)
# 2. ANGLE_BASED unwrap
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True)
# 3. average_islands_scale
bpy.ops.uv.average_islands_scale()
```
缺点: 1145个岛, 碎片多

**ZEN UV最佳(8.25/10)**:
```python
bpy.ops.uv.zenuv_auto_uv_unwrap(
    auto_detect_hard_edges=False, use_normal=False,
    use_texel_density=True, texel_density=10.0,
    mark_seam_edges=True, correct_self_intersecting=True,
    packing=True)
```
缺点: ~2000个碎片岛, 利用率60-70%

#### UV展开待探索方向

1. RizomUV GUI自动化(AutoHotkey, 绕过LUA限制)
2. Ministry of Flat CLI(未测试)
3. UVPackmaster 3(未测试)
4. libigl ARAP(未测试)
5. **标准低模模板Wrap**(建立标准UV低模, 用Surface Deform变形, 彻底绕过UV展开)
6. Blender Decimate替代QR(保留原始UV)
7. 高模法线引导接缝检测

---

## 四、两套方案的交叉点

### 4.1 为什么回退研究v1 Wrap

v3方案(QuadRemesher)的UV展开是核心卡点(8.5/10但碎块多)。如果v1方案(MetaHuman Wrap)能成功, 可以:
- 继承MetaHuman标准拓扑(面部环形线+关节布线)
- **直接继承MetaHuman的UV**(Body 32K/60K面, U 1.01-1.99第二通道), 避免UV展开问题
- 支持ARKit 52面绑(面部表情捕捉)

### 4.2 MetaHuman包裹 vs QR+UV

| 维度 | MetaHuman Wrap (v1) | QR + UV (v3) |
|------|---------------------|---------------|
| 拓扑 | MetaHuman标准(面部环形+关节) | QR均匀quad(无面部流线) |
| UV | 直接继承(无需展开) | 需要展开(碎块多) |
| 面数 | 32K/60K(低) | 90K(高) |
| 面部绑定 | ARKit 52兼容 | 不兼容 |
| 难点 | A-pose→T-pose变形 + 衣服干扰 | UV碎片化 |
| 完成度 | 头部0.4mm✓, 身体❌ | UV 8.5/10⚠️ |

### 4.3 推荐方案B: 身体包裹+头部用test01 v3.4方案（⚠️ 已放弃）

- 身体: MetaHuman Body wrap到Tripo(待解决A-pose→T-pose+衣服干扰)
- 头部: 用test01 v3.4方案(数值0.402mm/96.2%，但视觉质量差不可用)
- 包裹后直接继承MetaHuman拓扑+UV, 避免UV展开

---

## 五、方法对比汇总

### 5.1 拓扑传递方法对比

| 方法 | 原理 | 优点 | 缺点 | 姿势不同时 | 开源/免费 |
|------|------|------|------|-----------|-----------|
| **Shrinkwrap (NEAREST)** | 找最近表面点投影 | 简单快速 | 不看对应关系, 薄壁结构失败 | ❌ 崩溃 | ✅ Blender内置 |
| **Shrinkwrap (PROJECT)** | 沿法线射线投影 | 可控方向 | 破坏对称, 方向不准时失败 | ❌ 崩溃 | ✅ Blender内置 |
| **RBF (TPS)** | 薄板样条插值 | landmark精确 | 控制点稀疏时膨胀 | ✅ 可变形 | ✅ numpy实现 |
| **RBF (高斯)** | 高斯核插值 | landmark精确 | 同TPS, 膨胀略减 | ✅ 可变形 | ✅ numpy实现 |
| **ARAP** | As-Rigid-As-Possible | 保持局部形状, 不膨胀 | 需要初始对齐好, 计算复杂 | ✅ 可变形 | ⚠️ Blender有MINIMUM_STRETCH但效果差 |
| **Surface Deform** | 顶点级变形传递 | 可控范围 | 需要源目标姿势一致 | ❌ 需先对齐 | ✅ Blender内置 |
| **Laplacian变形** | 微分坐标保持 | 平滑过渡 | 不能大幅变形 | ⚠️ 小幅可 | ✅ Blender内置 |
| **R3DS Wrap/Faceform** | 控制点+法线投影 | 行业标准, 嘴唇/眼睑检测 | 付费$500/年 | ✅ 支持 | ❌ 付费 |
| **UE5 Mesh to MetaHuman** | 深度学习 | 全自动 | 闭源, 仅头部 | ✅ | ❌ 闭源 |
| **FLAME/DECA** | 参数化模型拟合 | 学术开源 | 需训练数据, 仅头部 | ✅ | ✅ 开源 |

### 5.2 关键发现

1. **Shrinkwrap和RBF是互补的**: Shrinkwrap做包裹(贴表面), RBF做变形(改姿势), 但都不能单独完成两步
2. **行业标准(R3DS Wrap)是分两步**: 先用控制点做变形(含姿势校正), 再用法线方向投影做包裹
3. **控制点密度是关键**: 16个点对全身太少, 头部478个MediaPipe点才够(但侧面/后脑仍有问题)
4. **衣服是独立问题**: 即使姿势对齐, 衣服表面也会干扰包裹(衣服下方无身体几何)
5. **头部和身体难度差异**: 头部有MediaPipe 478点(密集) + 姿势一致(都朝前), 身体只有16点(稀疏) + 姿势不同(A-pose vs T-pose)

---

## 六、当前状态与待解决问题

### 6.1 当前完成度

| 模块 | 完成度 | 状态 |
|------|--------|------|
| 头部Wrap | 40% | 数值0.402mm精度, 但耳朵/嘴唇/眼角扭曲+178自相交, 视觉质量不可用 |
| 身体Wrap | 10% | 所有方法(Shrinkwrap/RBF)均失败 |
| UV展开(QR网格) | 40% | 最佳8.5/10但碎块多, RizomUV background失效 |
| 高模修复 | 100% | repair.py通过 |
| 黏连检测 | 100% | adhesion.py通过 |
| QuadRemesher | 100% | 9万面quad |
| 烘焙 | 60% | 可运行但衣服干扰 |
| 骨骼绑定 | 100% | Mixamo 20骨骼 |
| GLB导出 | 100% | final.glb |

### 6.2 待解决问题（按优先级）

1. **身体Wrap的姿势变形**: A-pose→T-pose, 16个landmark不够, RBF膨胀
2. **衣服干扰**: Tripo高模含宽松衣服, Shrinkwrap被衣服表面吸引
3. **UV碎片化**: QR均匀quad网格导致接缝检测失效, 1145-2000个碎片岛
4. **头部Wrap薄壁结构**: 嘴唇/眼睑/耳廓的NEAREST投影拉到对侧
5. **RizomUV background限制**: ZomUnfold只做投影不做真正展开

### 6.3 行业调研结论（子代理调研补充）

#### ARAP是解决RBF膨胀的核心技术

ARAP(As-Rigid-As-Possible)变形通过**局部刚性约束**直接防止区域膨胀:
- 保持每个局部三角形尽可能刚性变换
- 控制点之间区域通过局部刚性约束自然变形,不会像RBF那样膨胀
- 即使控制点稀疏(16个),ARAP的容忍度也比RBF高得多

#### 行业标准是多步骤组合,不是单一方法

```
Step 1: RBF粗对齐 — 用landmark把A-pose低模大致对齐到T-pose
Step 2: ARAP局部刚性修正 — 消除RBF膨胀,保持手臂/腿形状
Step 3: Surface Deform精细贴合 — 同姿态下贴到高模表面
Step 4: 手动修正衣服区域
```

#### RBF膨胀的6种解决方案

1. 增加控制点密度(16→50+)
2. 换Wendland紧支撑核(`scipy.interpolate.RBFInterpolator(kernel='wendland')`)
3. 加正则化项(体积保持+Laplacian平滑)
4. RBF+ARAP混合(粗对齐+刚性修正)
5. 分区域RBF(头/躯干/四肢独立)
6. 用Non-Rigid ICP替代(自动加密控制点)

#### 开源工具推荐

| 工具 | Stars | 功能 | 适用性 |
|------|-------|------|--------|
| `libigl/libigl-python-bindings` | 369★ | ARAP实现,Python可用 | ⭐⭐⭐⭐⭐ |
| `oobma/ARAP-deformer` | 2★ | Blender专用ARAP插件 | ⭐⭐⭐⭐ |
| `mickare/Deformation-Transfer-for-Triangle-Meshes` | 213★ | 变形传递完整实现 | ⭐⭐⭐⭐ |
| `wuhaozhe/pytorch-nicp` | 275★ | GPU加速非刚性ICP | ⭐⭐⭐⭐ |
| `poly-hammer/character-dna-addon` | 275★ | MetaHuman DNA Blender导入 | ⭐⭐⭐⭐ |

#### 推荐工作流

```
增加控制点(16→50+) → RBF/Wendland粗对齐 → ARAP局部刚性修正(消除膨胀) → Surface Deform精细贴合 → 手动修正衣服区域
```

#### 其他有价值的发现

- **Deformation Transfer (Sumner 2004)**: 学术黄金标准,天然支持不同姿势,有Python实现(213★)
- **Non-Rigid ICP**: 自动建立密集对应关系,GPU加速,但对初始姿态敏感
- **头部wrap容易**: 无姿势差异+连续凸面+landmark密集+尺度一致
- **身体wrap困难**: A-pose/T-pose差异+衣服遮挡+控制点稀疏+体积差异

### 6.4 待探索方向（更新）

1. **ARAP变形**: Blender的MINIMUM_STRETCH效果差, 但libigl的ARAP可能更好
2. **增加landmark密度**: 在躯干侧面/手臂中段加更多点(20-30个), 减少RBF膨胀
3. **分段变形**: 躯干刚性对齐(差异小), 手臂RBF变形(差异大), 交界处混合
4. **骨骼驱动**: 给MetaHuman加骨骼(Auto-Rig Pro或手动), 旋转到T-pose, 再Shrinkwrap
5. **RizomUV GUI自动化**: AutoHotkey绕过LUA限制
6. **标准低模模板Wrap**: 建立标准UV低模, 用Surface Deform变形, 绕过UV展开

---

## 七、文件索引

### 7.1 方案文档

| 路径 | 内容 |
|------|------|
| `方案md记录/v1_MetaHumanWrap/MetaHumanWrap_完整档案.md` | v1方案完整档案 |
| `方案md记录/v1_MetaHumanWrap/research_report.md` | v1调研报告(含Wrap4D/UE5/FLAME对比) |
| `方案md记录/v2_镜像对称/` | v2镜像对称测试档案 |
| `方案md记录/v3_QuadRemesher/_方案与WBS/技术方案_全自动化版v3.md` | v3技术方案 |
| `方案md记录/v3_QuadRemesher/_方案与WBS/简化版方案缺陷分析.md` | v3缺陷分析(6个内部矛盾) |
| `方案md记录/v3_QuadRemesher/03自动UV/UV调研报告.md` | UV展开完整调研 |

### 7.2 测试文件

| 路径 | 内容 |
|------|------|
| `test01/scripts/pipeline/fit_v3.py` | 头部wrap管线(v3.4) |
| `test01/docs/research_report.md` | 头部wrap调研报告 |
| `test02/scripts/` | 身体wrap所有脚本(01-37号) |
| `test02/output/landmark_scene_v6.blend` | Tripo高模landmark(用户标记) |
| `test02/output/landmark_scene_mh_v2.blend` | MetaHuman landmark(用户标记) |
| `test02/output/wrap/wrapped_rbf_v1.blend` | RBF TPS变形结果 |
| `test02/output/wrap/wrapped_rbf_v2.blend` | RBF高斯变形结果 |
| `test03_SimplifiedPipeline/` | v3简化版管线(M1-M7) |
| `test03_SimplifiedPipeline/v6_run/01_repair.blend` | 高模修复结果 |
| `test03_SimplifiedPipeline/v5_run/final.glb` | 最终GLB输出 |

### 7.3 关键脚本

| 脚本 | 功能 | 状态 |
|------|------|------|
| `test01/scripts/pipeline/fit_v3.py` | 头部wrap(MediaPipe+Shrinkwrap+Laplacian) | ❌ 数值达标但视觉不可用 |
| `test02/scripts/37_wrap_v5_arms.py` | 身体wrap(旋转手臂+Shrinkwrap) | ❌ 失败 |
| `test03_SimplifiedPipeline/scripts/repair.py` | 高模修复 | ✅ 通过 |
| `test03_SimplifiedPipeline/scripts/adhesion.py` | 黏连检测 | ✅ 通过 |
| `test03_SimplifiedPipeline/scripts/launcher.py` | v3管线主控 | ⚠️ UV不达标 |
