# v3_QuadRemesher 交付

数字人管线 v3（Quad Remesher 方案）最终可交付资产。

## 目录结构

按里程碑分阶段：

```
01高模修复与黏连检测/   ← 当前已交付
02QuadRemesher拓扑/     ← 待交付
03自动UV/               ← 待交付
04纹理烘焙/             ← 待交付
05骨骼绑定/             ← 待交付
06GLB导出/              ← 待交付
07管线集成/             ← 待交付
```

## 01高模修复与黏连检测

| 子目录 | 内容 |
|---|---|
| `models/` | 三份修复后的高模 blend（tripoTpose / tripoApose / hunyuanApose） |
| `screenshots/` | 每份模型的 front / side / three_quarter 三视角截图 |
| `scripts/` | 完整可运行的修复管线代码（repair + adhesion + QA + 渲染） |
| `docs/` | 高模修复操作手册 v16（含管线流程、难题与解决方案） |

### 快速验证

```
cd scripts
set B="D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
%B% --background ..\models\tripoTpose_01_repair.blend --factory-startup --python repair_qa.py
```

末行 `总评: PASS` 即通过。

### 三模型当前质检数据

| 模型 | 顶点 | 面数 | 非流形 | 边界 | 身高 |
|---|---|---|---|---|---|
| tripoTpose | 965,018 | 1,930,105 | 1 | 0 | 0.976 |
| tripoApose | 942,992 | 1,886,029 | 8 | 4 | 0.980 |
| hunyuanApose | 749,782 | 1,499,588 | 0 | 0 | 1.163 |

## 参考

- 完整调研报告与方案文档：`..\方案md记录\v3_QuadRemesher\`
- 测试工作目录（含过程文件）：`..\test03_SimplifiedPipeline\`
- 原始 AI 高模：`..\原始模型\AI生成高模\`
