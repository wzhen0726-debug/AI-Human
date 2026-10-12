# QR 引擎：旋钮、密度图与边界/面数硬限制（QuadRemesher 1.3.0.3452，本机安装）

引擎 = `…/extensions/user_default/quadremesher/EngineWin/xremesh.exe`（与 ZBrush ZRemesher 同源）。
面板只暴露 11 键；DLL 里还有一批可用键。注入方式：手写 RetopoSettings + 直接调 `xremesh.exe -s`，
或在管线脚本里加 `QR_SET_<键>=<值>` 透传通道。

## 键表

面板/管线已在用（11）：
`HostApp / FileIn / FileOut / ProgressFile / TargetQuadCount / CurvatureAdaptivness / ExactQuadCount /
UseVertexColorMap / UseMaterialIds / UseIndexedNormals / AutoDetectHardEdges`

引擎里可注入（节选，实测有效）：
`TargetEdgeLength / TargetQuadCountAsInputPercentage / FreezeBorders / FreezeBordersCoef / FollowBorders /
VarDensityRatio / NumPointCirc / MaxQuadRatio / DenoiseStrength / UsePolygonGroups / UseSmoothingGroups /
UseHardEdgeFlags / UseFacesSelections / UseEdgesSelections / AutoDetectHardEdges_Angle / SymTopo /
MaxNumThread / PreProcess_WeldPoints / PostProcess_SplitPointsOnCreasedNormals /
SmartMergeCADFacesGroups / RetopoNodeName`

- 本版本**无 Guides/Curves 键** → 曲线/边引导不可用。
- 取键方法：用 `strings` 扫引擎 dll 找键块（全量、比翻文档快）。

## 顶点色密度图（指定区域加密且保持四边流）

- 必须 `UseVertexColorMap=1` **且**输入真有顶点色数据；只开开关无效果（实测与基线同级）。
- 官方画笔域：painted density ∈[0.25, 4.0]（颜色映射 红=(1,1-n,1-n) 青=(1+n,1,1)）；`VarDensityRatio` 是可注入的加密倍数上限。
- 实测配方（眼周加密）：`QR_DENSITY_MAP=1 QR_DENS_R_MM=10~12 QR_DENS_PLATEAU=0.3~0.5 QR_SET_VarDensityRatio=4`
  → 眼周 4mm 带 100% 四边、面均边长加密 1.7~2.7×，全模型面数几乎不变（+0.6% 内）。
- **边界不响应**：rim 边长中位只有 2.17→1.96mm 量级、转角 max 68.7/83.1°→44/53° 量级。密度图治不了“边界采样粗”。

## FreezeBorders：能锁边界，但全局面尺寸跟着炸

- 语义（与 ZBrush ZRemesher 同源）：冻结边界时沿边界布点，**边界点距 = 全局面尺寸**。
- 实测：0.22mm 真值边界 + FreezeBorders=1 → 引擎输出 ≈4770 万面（预算 295×）、745MB 级 FBX，导入 24 分钟未完；
  先把边界粗化到 ~1.2~1.4mm 再冻结 → `Error: Remeshing failed. (BadInput)`（FreezeBorders=0 对照同样 BadInput → 该预处理本身不可用）。
- 结论：本版本引擎**没有“只在边界局部加密”的旋钮**——开放边界采样与全局四边形尺寸是同一个量。

## 面数档位的代价（实测对照，评估“涨面数换锐度”前必看）

| 档位 | 实收面数 | rim 采样 | 内眼角转角 | 副作用 |
|---|---|---|---|---|
| 150k | ~161k | L38/R37 点、2.17/1.76mm | ~50~68° | 长直弦在眼角折成尖角（“平口切断”） |
| 650k | ~604k（3.72×） | L64/R68 点、1.08/1.35mm | 仍 ~50.7° | 细长面 10×/5×、极点 364→500、扇顶点 21→95、blend 6.2→23MB；下游 UV/烘焙/权重全按面数放大 |

→ 单纯提面数只把“长直弦”换成“密集短折线”，不解决内眼角曲率。

## 边界形态缺陷的治理（后续实测）

长直弦/贴环微面已在边界层面治理：**形态门**（四眼角：转角≤40°/切角偏离≤0.30mm/最长环边≤8mm/点-真值≤0.40mm/针状面≤1.5mm）
+ **修环**（吸真值+微量插点+尖角开口）+ **顺序**（修环排在建碗后）+ 多轮选优；纯 QR 轮 0/9 过形态门 → 修环必跑。
材质引导（UseMaterialIds + rim 外材质槽）实测更差（带最小边 0.017mm、FBX ~11min）→ 不用。
完整协议：`references/canthus-boundary-shape-gate.md`。
