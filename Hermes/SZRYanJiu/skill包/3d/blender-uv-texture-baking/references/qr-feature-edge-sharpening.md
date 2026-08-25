# QR低模特征边缘锐化 — 眼窝rim案例

**日期**: 2026-08-24 | **状态**: ✅ 已验证（vision确认锐利）
**适用**: QuadRemesher等自动重拓扑在精细特征（眼窝rim、唇缝、鼻孔缘）处布线不够锐利时

## 问题

QR全局自动布线在眼窝rim（眼睑开口边缘）处产生模糊平滑的边缘，不够锐利。用户要求锐利的眼睑交界。

## 已试方案（5种，全部失败）

| 方案 | 原理 | 结果 | 失败原因 |
|---|---|---|---|
| 锐边标记 | 给rim边标记锐边 | 无效 | rim面太少(L19/R32个顶点)，折角做不出来 |
| 局部加密 | subdivide rim带 | 布线乱掉 | 无差别细分产生碎面/三角面/极点，拓扑报废 |
| 材质边界 | QR UseMaterialIds=1 | rim锐利但几何粗糙 | QR在材质边界强制布线，产生锯齿/撕裂/碎块 |
| 高模预锐化 | rim加0.3mm倒角让QR检测 | 无效 | QR AutoDetectHardEdges检测不到小倒角 |
| rim环形布线 | 手动建rim环+桥接 | 锐利但突兀 | rim环是硬切几何框，与皮肤不融合，需大量手工调 |

## ✅ 解决方案：低模rim倒角（0.5mm）

**核心思路**: 不改QR布线，在低模rim处加几何倒角（Bevel Modifier），让rim有真实的几何锐利度。

### 步骤

1. **找rim带边**: 距rim轮廓<3mm的边（用rim轮廓JSON的3D点）
2. **设置倒角权重**: `bevel_weight_edge`属性=1.0（标记哪些边要倒角）
3. **加Bevel修改器**: width=0.0005(0.5mm), segments=2, limit_method='WEIGHT'
4. **应用修改器**: 固化几何到mesh
5. **UV展开**: 在应用倒角后的mesh上做UV
6. **烘焙**: 用这版低模烘焙

### 关键脚本（rim_bevel.py）

```python
# 1. 找rim带边
rim_edges = []
for e in me.edges:
    mid = (mw @ me.vertices[e.vertices[0]].co + mw @ me.vertices[e.vertices[1]].co) / 2
    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"])
        if np.linalg.norm(mid[None,:] - rim, axis=1).min() < 0.003:
            rim_edges.append(e); break

# 2. 设置倒角权重(直接用mesh边索引, 不用bmesh)
bw_attr = me.attributes.get("bevel_weight_edge")
if bw_attr is None:
    bw_attr = me.attributes.new(name="bevel_weight_edge", type='FLOAT', domain='EDGE')
for e in rim_edges:
    bw_attr.data[e.index].value = 1.0

# 3. 加Bevel修改器
bev = head.modifiers.new("RimBevel", 'BEVEL')
bev.width = 0.0005   # 0.5mm
bev.segments = 2
bev.limit_method = 'WEIGHT'
```

### 关键坑

1. **`bevel_weight_edge`属性设置**: 不能用`e.bevel_weight = 1.0`（BMEdge没这个属性），必须用`me.attributes["bevel_weight_edge"].data[e.index].value = 1.0`。
2. **UV展开会重建mesh**: 倒角权重属性会丢。必须先**应用倒角修改器**（固化几何），再UV展开。
3. **倒角宽度**: 0.5mm是验证过的值。太小（0.3mm）QR检测不到，太大（>1mm）改变眼窝形状。
4. **rim轮廓来源**: 用01A手动标记的`eyelid_contour_manual.json`（72点/侧），不是自动检测。

## 验证结果

- **vision确认**: rim边缘清晰锐利、折角明显、倒角赋予厚度和立体感
- **与模糊平滑版对比**: 明显改善
- **面数变化**: 143308→143717（+409面，可接受）

## 后续方案（如需更锐利）

- **法线烘焙**: 高模rim的锐利折角烘焙到法线图上，低模渲染时rim看起来锐利
- **手动重拓扑**: 用RetopoFlow沿眼睑开口做环形edge loop（工作量大，约1-2小时）

## 相关文件

- 解决方案脚本: `02QuadRemesher拓扑/scripts/rim_bevel.py`
- rim倒角版低模: `02QuadRemesher拓扑/02_qr_150k_rim_bevel.blend`
- rim问题备忘录: `02QuadRemesher拓扑/rim问题_技术备忘录.md`
