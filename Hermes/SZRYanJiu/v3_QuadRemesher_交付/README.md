# v3_QuadRemesher 交付

数字人管线 v3（Quad Remesher 方案）最终可交付资产。每个步骤目录内自带可交付的 py 脚本（`scripts/` 子目录）+ 说明 README + 产物（blend/png/fbx 二进制走 .gitignore，本地保留）。

> 最后更新: 2026-08-05

## 目录结构

```
01高模修复与黏连检测/   ← ✅ 已交付（修复管线：repair + adhesion + QA + 渲染）
02QuadRemesher拓扑/     ← ✅ 已交付（QR 自动重拓扑）
03自动UV/               ← ✅ 已交付（Smart UV Project）
04纹理烘焙/             ← ✅ 已交付（Diffuse + Normal 4K）
05骨骼绑定/             ← 规划中（Mixamo 绑定）
06GLB导出/              ← 规划中
07管线集成/             ← 规划中
```

每个步骤的标准结构：

```
NN步骤名/
├── README.md            # 方案说明、参数、输入输出、验证结果
├── scripts/             # ★ 可交付的 py 脚本（可独立复跑）
├── *.blend / *.fbx      # 产物（二进制，本地保留，不入 git）
└── docs/                # （01 特有）操作手册
```

## 各步骤脚本一览

| 步骤 | 脚本 | 功能 |
|---|---|---|
| 01 | `01高模修复与黏连检测/scripts/run_repair.py` | 一键入口：GLB → 修复+黏连+焊接 → blend |
| 01 | `01高模修复与黏连检测/scripts/repair.py` | 网格修复主模块（foot_score v3 朝向 + Taubin + final_weld_for_qr） |
| 01 | `01高模修复与黏连检测/scripts/adhesion.py` | 黏连检测与推开（衣物-身体嵌套分离） |
| 01 | `01高模修复与黏连检测/scripts/repair_qa.py` | 质检（非流形/边界/碎面/刀片面等） |
| 01 | `01高模修复与黏连检测/scripts/render_screenshot.py` | 三视角截图渲染 |
| 02 | `02QuadRemesher拓扑/scripts/02_qr_auto.py` | subprocess 直调 xremesh.exe（绕过 modal 算子） |
| 03 | `03自动UV/scripts/03_auto_uv.py` | Smart UV Project（66°/margin 0.01） |
| 04 | `04纹理烘焙/scripts/04_bake.py` | Cycles Selected-to-Active 烘焙 Diffuse+Normal 4K |

## 01高模修复与黏连检测

| 子目录 | 内容 |
|---|---|
| `models/` | 修复后高模 blend（tripoTpose / tripoApose / hunyuanApose）+ 当前主管线 `01_highpoly_repair.blend` |
| `screenshots/` | 三视角截图与历次问题排查截图 |
| `scripts/` | 完整可运行的修复管线代码 |
| `docs/` | 高模修复操作手册 v16/v20（含 12 个难题的根因与解法） |

### 快速验证

```
cd 01高模修复与黏连检测/scripts
set B="D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
%B% --background --factory-startup --python run_repair.py -- <input.glb> <output.blend>
```

或用 QA 检查已有产物：`%B% --background <blend> --factory-startup --python repair_qa.py`，末行 `总评: PASS` 即通过。

### 三模型质检数据（v16 时期）

| 模型 | 顶点 | 面数 | 非流形 | 边界 | 身高 |
|---|---|---|---|---|---|
| tripoTpose | 965,018 | 1,930,105 | 1 | 0 | 0.976 |
| tripoApose | 942,992 | 1,886,029 | 8 | 4 | 0.980 |
| hunyuanApose | 749,782 | 1,499,588 | 0 | 0 | 1.163 |

## 02QuadRemesher 拓扑

QR 引擎（xremesh.exe）全自动重拓扑：193万三角面 → 14.9万四边面（100% quad）。详见目录内 README（含 SymAxis 关闭决策：纹理不对称导致烘焙错位，改用自然拓扑）。

## 03自动UV

Smart UV Project：`angle_limit=66°`, `island_margin=0.01`, `correct_aspect=True`。边缘角度>55°的接缝方案在高面数上产生碎岛，已弃用。

## 04纹理烘焙

Cycles Selected-to-Active：Diffuse + Normal 双 4K，`cage_extrusion=0.01`, `max_ray_distance=0.05`（防衣服穿透见皮肤）。产物：`04_diffuse_4k.png` / `04_normal_4k.png` / `05_for_mixamo.fbx`。

## 参考

- 完整调研报告与方案文档：`..\方案md记录\v3_QuadRemesher\`
- 测试工作目录（含过程文件）：`..\test03_SimplifiedPipeline\`
- 原始 AI 高模：`..\原始模型\AI生成高模\`
