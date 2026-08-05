# AI-Human — AI自动化数字人处理

数字人全流程管线研究仓库：从 AI 生成高模（Tripo / 混元等）出发，经高模修复、自动重拓扑、UV 展开、纹理烘焙、骨骼绑定，最终产出可绑定、可动画的标准数字人资产（.glb）。

**目标管线**：Tripo AI 高模 → 高模修复（旋转/焊接/非流形/黏连）→ Quad Remesher 重拓扑 → 自动 UV → 纹理烘焙 → Mixamo 身体绑定 + ARKit 52 表情 → .glb 输出

> 最后更新：2026-08-05 ｜ 当前主方案：**v3 QuadRemesher 管线**（01~04 已交付，05 骨骼绑定进行中）

## 版本独立性说明

v1 / v2 / v3 / v4 是**四个相互独立的技术方案**，不是同一方案的迭代版本，资产与脚本互不依赖：

| 版本 | 方案 | 状态 |
|---|---|---|
| v1 MetaHuman Wrap | 扫描高模 → MetaHuman 模板 wrap | ⏸ 暂停：头部 wrap 数值达标（0.402mm/96.2%）但视觉不可用；身体 wrap 9 种方法全部失败（根因：Tripo 衣服嵌套 + 53.1% 法线反转） |
| v2 镜像对称 | RANSAC 谱匹配 / ZBrush 智能对称 | 参考（独立工具模块，调研完成） |
| **v3 QuadRemesher** | 修复→QR拓扑→UV→烘焙→绑定→GLB | ✅ **当前主方案**，01~04 已交付 |
| v4 前瞻性 | MVP → 3D分割+ARAP → SMPL-X | 远期规划 |

完整档案（含失败根因分析）见 `Hermes/SZRYanJiu/方案md记录/`。

## 目录结构

```
├── 01/                              # Blender MCP 桥接（opencode stdio ↔ Blender TCP:9876）
├── Scan_001/                        # 扫描原始资产（glb/zpr，二进制不入git）
├── Hermes/SZRYanJiu/                # ★ 主研究目录
│   ├── 全流程文档/                   # 技术方案总览（docx：规划 / v4 / v7）
│   ├── 方案md记录/                   # 方案档案与结论沉淀（v1~v4 全记录 + 工作记录）
│   ├── v3_QuadRemesher_交付/        # ★★ 主管线交付资产（每步含 scripts/ 可交付脚本）
│   ├── 原始模型/                     # AI高模、MetaHuman低模、PYWrap对齐数据（本地保留）
│   ├── test01/                      # 头部拓扑测试：MediaPipe 478点 + 特征点对齐
│   ├── test02/                      # MVP 管线测试：decimate/QR/UV/烘焙/FBX导出
│   └── test03_SimplifiedPipeline/   # 高模修复管线测试（repair + adhesion + QA）
└── Zed/
    ├── ShiJueShiBieMesh/            # 视觉识别 Mesh（MediaPipe 面部/几何打点实验）
    ├── Wrap4D/复刻/                  # Wrap4D 逆向复刻（wrapclone 引擎 + PyQt GUI + Blender 插件）
    └── ZaWu001/                     # 杂项实验
```

## v3 主管线（v3_QuadRemesher_交付）

每步目录内自带**可交付 py 脚本**（`scripts/`）+ 方案 README + 产物。

| 步骤 | 内容 | 脚本 | 状态 |
|---|---|---|---|
| 01 高模修复与黏连检测 | foot_score v3 旋转矫正 + 焊接 + 非流形/黏连修复 + final_weld_for_qr + QA | `run_repair.py` / `repair.py` / `adhesion.py` / `repair_qa.py` | ✅ |
| 02 QuadRemesher 拓扑 | xremesh.exe 全自动重拓扑，14.9万四边面 100% quad | `02_qr_auto.py` | ✅ |
| 03 自动 UV | Smart UV Project（66°/margin 0.01） | `03_auto_uv.py` | ✅ |
| 04 纹理烘焙 | Cycles Selected-to-Active，Diffuse + Normal 4K | `04_bake.py` | ✅ |
| 05 骨骼绑定 | Mixamo 标准骨骼（几何分析定位关节） | — | 规划中 |
| 06 GLB 导出 | 绑定+贴图导出 .glb | — | 规划中 |
| 07 管线集成 | 全流程一键串联 | — | 规划中 |

**关键技术修复**：
- 01 输出前 `final_weld_for_qr()` 强制焊接（172,285 重复顶点 + 516,960 开放边界边 → 焊后边界边 11 条），解决 QR xremesh 预处理卡死 21% 问题
- foot_score 旋转判据：用两端横截面积差区分身高轴与臂展轴（T-pose 臂展≈身高，"最大维度=身高"判据失效）
- QR 关闭 SymAxis 对称：纹理不对称会导致烘焙错位，改用自然拓扑

## Wrap4D 复刻（Zed/Wrap4D）

逆向复刻 Wrap 2025 的包裹引擎：RBF/相似变换初对齐 → 外层 ICP（重找对应 + 扩半径）→ 内层优化（平滑衰减求解），参数结构对齐官方 Gallery 默认值。含 PyQt GUI、Blender 双向桥接插件与单元测试。

## 环境

- Blender 5.1 + 插件：Quad Remesher、Auto-Rig Pro、Better FBX、MACHIN3tools
- Python 3.11：numpy / scipy / trimesh / MediaPipe（face_landmarker / pose_landmarker）
- Windows，git 走代理推送

## 大资产策略

受 GitHub 100MB 单文件限制，所有二进制模型/贴图资产（`.blend` `.fbx` `.glb` `.png` `.zpr` 等，见 `.gitignore`）不入库，本地保留于原路径；目录结构用 README 占位保持可见。代码（`.py`）与文档（`.md`/`.docx`）全部入库。

