# 版本三：简化版Quad Remesher全自动方案 — 完整技术档案（上）

## 环境
同v1，测试路径：`test02\`

## 项目目标
照片 → AI高模 → 几何修复 → 黏连修复 → Quad Remesher(20-25万面) → 自动UV(边缘角度接缝+Unwrap+Pack) → 烘焙(Diffuse+Normal) → Mixamo绑定 → GLB。保留衣服头发，不做对称，不做面绑，全自动化，8-10周。

## 与v1的核心差异

| 维度 | v1 MetaHuman Wrap | v3 简化版 |
|------|------|------|
| 拓扑 | MetaHuman模板wrap(手动) | Quad Remesher(自动) |
| 面数 | 2-5万面 | 20-25万面 |
| 面部绑定 | ARKit 52 | 无 |
| 对称化 | 高模对称化(ZBrush) | 不做 |
| 衣服 | 去除(4周) | 保留 |
| 头发 | 去除 | 保留 |
| 眼球 | 标准模板装配 | 保留网格内 |
| 工期 | 21周 | 8-10周 |
| 自动化 | 部分手动 | 全自动 |

## 方案来源
用户提供两份文档作为基准：
1. `项目WBS_修正版.md`：原始WBS，6-8周，30万面，Smart UV Project，关闭Symmetry X
2. `整体技术方案_修正版.md`：对应技术方案

## 调研过程

### 调研1：Quad Remesher在含衣服模型上的质量
- 来源：Exoside官方、80.lv评测、Blender Artists FAQ
- Quad Remesher Adaptive Size模式自动在高曲率区域（褶皱、面部）分配更高面密度
- 30万面处于Mixamo边界值（社区经验25-50万面可上传），建议**20-25万面**
- 可通过Material ID区分身体/衣服引导布线沿接缝走
- 衣服和身体是同一mesh，重拓扑后衣服区域布线基本规整
- 腋下/胯部复杂区域可能需要顶点色辅助

### 调研2：Mixamo对含衣服模型的绑定
- 紧身/半紧身衣（T恤、薄外套）自动权重质量70-80%
- 宽松服装（裙子、长袍）自动权重差，需3-5天手动修正
- **结论：拍照必须穿紧身衣/泳衣**

### 调研3：Symmetry X
- 原WBS关闭Symmetry X（因为衣服款式不对称）
- 但关闭后低模左右不对称，影响Mixamo绑定精度+权重修正工作量翻倍
- **结论：拍照穿紧身衣（款式对称），恢复Symmetry X开启**

### 调研4：Smart UV Project vs 自动边缘角度接缝
- 原WBS使用Smart UV Project（0.5周）
- 调研发现Smart UV Project接缝不可控+岛碎片化严重+无对称性保证→**不可用于生产**
- 替代方案：**自动边缘角度接缝+标准Unwrap+Pack Islands**
  - 计算二面角→>55°标记为接缝→X=0对称轴接缝→Angle Based Unwrap→pack_islands→average_islands_scale
  - 纯Blender Python API，零外部依赖，100%自动化
  - 已有实现脚本：`C:\Users\Liyunzhong\auto_uv_pipeline.py`
- 调研还覆盖了：UVPackmaster（$29-49 GPU版，有Python SDK）、RizomUV（$300+/年，Lua API）、Magic-UV（免费，无自动接缝）
- 最终选定：自动边缘角度方案，0.5-1周

### 调研5：眼球分离
- 原WBS删除眼球分离（简化流程）
- 用户纠正：Quad Remesher保留所有几何体，眼球自然被重拓扑，无需分离
- **结论：不分离眼球**

### 调研6：黏连检测与修复
- MediaPipe Holistic 33个身体关键点检测，在AI 3D渲染图上PCK@0.2预计85-92%
- 最小距离算法参考：BVH加速+三角面片距离查询
- 修复方案：沿法线推开→Laplacian变形+权重衰减→Taubin平滑
- 风险：修复后产生新自相交概率30-50%，需迭代小步长
- 修复必须在Quad Remesher之前（Remesher要求几何正确）
- 拍照时双腿分开肩宽可大幅降低黏连概率

### 调研7：纹理烘焙
- 烘焙距离0.5-2cm需Cage模式
- 高模含衣服但低模不含→烘焙投射光线可能命中衣服而非身体→需分离高模+Cage控制
- Normal贴图可捕捉表面凹凸但不能修复轮廓
- 30万面低模：Diffuse+Normal双贴图，GLB约25-40MB
- GLB导出正常（无BlendShape不影响）

---

# 版本三：简化版Quad Remesher全自动方案 — 完整技术档案（中）

## 原WBS的6个内部矛盾

| # | 原WBS | 矛盾 | 修正 |
|---|------|------|------|
| 1 | 30万面 | Mixamo边界值，失败风险 | 20-25万面 |
| 2 | 关闭Symmetry X | 绑定精度差，权重工作量翻倍 | 紧身衣恢复对称 |
| 3 | Smart UV Project | 接缝不可控+无对称→不可生产 | 自动边缘角度接缝+标准Unwrap(全自动) |
| 4 | 删除眼球分离 | Quad Remesher保留眼球，无需分离 | 不分离 |
| 5 | 未考虑衣服烘焙干扰 | 高模衣服影响投射 | 分离高模+Cage |
| 6 | 宽松衣未约束 | 权重质量差 | 拍照穿紧身衣 |

## 工期对比

| 阶段 | 原WBS | 修正版 | 原因 |
|------|------|------|------|
| Remesher | 1周 | 1.5周 | 面数调优+对称验证 |
| UV展开 | 0.5周 | 0.5-1周 | 自动边缘角度接缝替代Smart UV |
| 纹理烘焙 | 1.5周 | 1.5周 | 增加高模分离+Cage |
| 绑定 | 1.5周 | 1.5周 | 不变 |
| 总工期 | 6-8周 | 8-10周 | 修正5个矛盾 |

## 最终技术方案（全自动化版v3）

### 阶段1：高模获取（1.5周）
- 拍照规范：**必须紧身衣/泳衣**，双腿肩宽预防黏连，双臂水平伸直(T-pose)，正面+侧面+背面4视角
- AI生成：混元3D/Tripo，GLB格式，50-200万面

### 阶段2：几何修复（1.5周）
- bmesh fill_holes填补破洞
- dissolve_degenerate+remove_doubles清理乱面
- Voxel Remesh体素化重建
- Laplacian Smooth表面平滑（面部保护）

### 阶段3：黏连修复（1.5周）
- MediaPipe Holistic 33个身体关键点检测（多视角渲染）
- 大腿内侧顶点最小距离<5mm判定黏连
- 沿法线推开+Laplacian变形（迭代小步长+每步验证）
- 修复在Quad Remesher之前（Remesher要求几何正确）

### 阶段4：Quad Remesher（1.5周）
- 目标面数：20-25万面
- Symmetry X：开启（紧身衣款式近似对称）
- Preserve Sharp Edges：开启
- Adaptive Size：开启
- Material ID区分引导布线（可选）
- 决策点DP-3：面数达标/无破面/锐边保留→通过

### 阶段5：自动UV展开（0.5-1周）
- 自动标记接缝：边缘角度>55°→mark_seam
- X=0对称轴接缝：确保左右UV对称
- Angle Based Unwrap
- pack_islands(rotate=True)自动优化
- average_islands_scale均衡密度
- 纯Blender Python，零外部依赖
- 决策点DP-4：拉伸<20%，接缝在隐藏位置→通过

### 阶段6：纹理烘焙（1.5周）
- 高模衣服/身体分离
- Cage Object控制投射方向
- Selected to Active，烘焙距离0.5-2cm
- Diffuse Color + Normal贴图
- 决策：错位/接缝/黑斑检查

### 阶段7：绑定（1.5周）
- Mixamo云端自动绑定（主力）
- Auto-Rig Pro Smart备选
- 权重修复：跨腿X坐标重分配+独占平滑+全局平滑
- 决策点DP-5：走路/挥手无严重穿模→通过

### 阶段8：GLB导出（0.5周）
### 阶段9：Pipeline集成（2周）
- pipeline.py主控+config.json+Checkpoint
- 端到端测试5组，通过率>80%

---

# 版本三：简化版Quad Remesher全自动方案 — 完整技术档案（下）

## 里程碑时间表

| 周 | 里程碑 | 交付物 | 决策点 |
|---|-------|--------|-------|
| W1 | M0启动 | 方案定稿 | — |
| W2-3 | M1高模+修复 | generate.py, repair.py | DP-1 Mixamo测试 |
| W3-4 | M2黏连修复 | clamp_fix.py | DP-2 黏连效果 |
| W4-5 | M3 Remesher | 20-25万面低模 | DP-3 面数质量 |
| W5-6 | M4 UV自动 | UV完成 | DP-4 UV接缝/拉伸 |
| W6-7 | M5烘焙 | Diffuse+Normal | — |
| W7-8 | M6绑定 | GLB含骨骼 | DP-5 绑定质量 |
| W8-9 | M7 Pipeline | 测试报告 | DP-6 验收 |
| W9-10 | M8交付 | ZIP工具包 | — |

## 决策点

| # | 时间 | 内容 | 通过标准 | 未通过 |
|---|------|------|---------|-------|
| DP-1 | W2末 | Mixamo可行性 | 3组绑定成功 | 切ARP |
| DP-2 | W3末 | 黏连修复 | 大腿间隙>1cm | 调拍照 |
| DP-3 | W5中 | Remesher | 20-25万面/无破面 | 调参数 |
| DP-4 | W6中 | UV质量 | 拉伸<20%，接缝隐藏 | 调角度阈值 |
| DP-5 | W8中 | 绑定 | 走路/挥手正常 | 手动修正+0.5周 |
| DP-6 | W9中 | 端到端 | >80%通过率 | 延长1周 |

## 质量预期

| 维度 | 质量 | 说明 |
|-----|------|------|
| 身体动画 | ✅ 良好 | 走路/挥手/转身正常，20-25万面关节变形良好 |
| 面部 | ⚠️ 静止 | 无BlendShape，无面捕 |
| 衣服跟随 | ⚠️ 可接受 | 紧身衣跟随好，宽松衣大动作可能穿模 |
| 头发 | ⚠️ 刚性 | 跟随头部运动，无物理 |
| 眼球 | ⚠️ 静态 | 镶嵌在网格内，不能转动 |
| 对称性 | ✅ 好 | 紧身衣+Symmetry X开启 |
| 文件大小 | 适中 | GLB约25-40MB |

## 风险矩阵

| 风险 | 等级 | 概率 | 应对 |
|------|------|------|------|
| Mixamo绑定失败 | 中 | 30% | 切Auto-Rig Pro Smart |
| 黏连修复不彻底 | 中 | 30% | 拍照预防+迭代修复 |
| 烘焙纹理质量差 | 中 | 20% | 分离高模+Cage |
| 自动UV接缝可见 | 低 | 15% | 非AAA可接受，角度>55°接缝在隐藏位置 |
| 宽松衣穿模 | 中 | 25% | 拍照穿紧身衣预防 |
| 端到端超时 | 低 | 15% | Checkpoint分阶段重试 |

## 关键API/技术备忘

自动UV实现：
```python
# 边缘角度检测→标记接缝
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.edges_select_sharp(sharpness=0.96)  # ~55°阈值
bpy.ops.mesh.mark_seam(clear=False)

# 补充对称轴接缝（X≈0的边）
bpy.ops.mesh.select_all(action='DESELECT')
# 选择X≈0的边→mark_seam

# 展开+打包
bpy.ops.uv.unwrap(method='ANGLE_BASED')
bpy.ops.uv.pack_islands(rotate=True)
bpy.ops.uv.average_islands_scale()
```

Quad Remesher调用：
```python
bpy.ops.quadremesher.remesh(
    target_count=250000,
    use_symmetry_x=True,
    detect_hard_edges=True,
    adaptive_size=True
)
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `test02\技术方案_全自动化版v3.md` | 最终技术方案 |
| `test02\项目WBS_全自动化版v3.md` | 最终WBS（8-10周） |
| `test02\简化版方案缺陷分析_上.md` | 原WBS的6个矛盾分析（1-4） |
| `test02\简化版方案缺陷分析_下.md` | 原WBS的6个矛盾分析（5-8）+工期修正 |
| `test02\档案_v3_QuadRemesher_上.md` | 本文档上半部分 |
| `test02\档案_v3_QuadRemesher_中.md` | 本文档中部 |
| `test02\档案_v3_QuadRemesher_下.md` | 本文档下半部分 |
| `C:\Users\Liyunzhong\auto_uv_pipeline.py` | 自动UV脚本（调研产出） |