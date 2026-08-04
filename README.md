# AI-Human — AI自动化数字人处理

数字人全流程管线研究仓库：从 AI 生成高模（Tripo 等）出发，经高模修复、自动重拓扑、UV 展开、纹理烘焙，最终产出可绑定、可动画的标准数字人资产（.glb）。

**目标管线**：Tripo AI 高模 → 去衣去发 → 高模修复 → 重拓扑 → UV/烘焙 → Mixamo 身体绑定 + ARKit 52 表情 → .glb 输出

## 目录结构

```
├── 01/                              # Blender MCP 桥接（opencode stdio ↔ Blender TCP:9876）
├── Hermes/SZRYanJiu/                # 主研究目录
│   ├── 全流程文档/                   # 技术方案总览（docx：规划 / v4 / v7）
│   ├── 方案md记录/                   # 方案档案与结论沉淀（v1~v4 全记录）
│   ├── v3_QuadRemesher_交付/        # ★ 主管线交付资产（01修复→02拓扑→03UV→04烘焙）
│   ├── 原始模型/                     # MetaHuman 低模、PYWrap 对齐数据等基础资产
│   ├── test01/                      # 头部拓扑测试：MediaPipe 478点 + 特征点对齐
│   ├── test02/                      # MVP 管线测试：decimate/QR/UV/烘焙/FBX导出
│   └── test03_SimplifiedPipeline/   # 高模修复管线测试（repair + adhesion + QA）
└── Zed/
    ├── ShiJueShiBieMesh/            # 视觉识别 Mesh（MediaPipe 面部/几何打点实验）
    └── Wrap4D/复刻/                  # Wrap4D 逆向复刻（wrapclone 引擎 + PyQt GUI + Blender 插件）
```

## 研究演进（v1 → v4）

| 阶段 | 方向 | 结论 |
|---|---|---|
| v1 MetaHumanWrap | 扫描高模 → MetaHuman 模板 wrap | 头部 wrap 数值达标（0.402mm / 96.2%）但视觉质量差，不可用于生产；身体 wrap 9 种方法全部失败（根因：Tripo 衣服嵌套 + 53.1% 法线反转），放弃 |
| v2 镜像对称 | 独立对称模块 | RANSAC 谱匹配 / ZBrush 智能对称调研完成 |
| v3 QuadRemesher | **主管线**：修复→QR拓扑→UV→烘焙 | 01~04 步骤已交付（详见下节） |
| v4 前瞻性 | 三阶段演进路线 | MVP → 分割+ARAP → SMPL-X 工业级管线 |

完整档案见 `Hermes/SZRYanJiu/方案md记录/`（含失败记录与根因分析）。

## v3 主管线（v3_QuadRemesher_交付）

| 步骤 | 内容 | 状态 |
|---|---|---|
| 01 高模修复与黏连检测 | 旋转矫正 + 焊接 + 非流形/黏连修复 + QA 渲染 | ✅ 交付（tripoT/A、hunyuanA 三模型） |
| 02 QuadRemesher 拓扑 | QR 自动重拓扑，235,660 面 100% quad | ✅ 交付 |
| 03 自动 UV | 边缘角度接缝自动展开 | ✅ 交付 |
| 04 纹理烘焙 | Diffuse + Normal 4K 烘焙 | ✅ 交付 |
| 05~07 绑定 / GLB导出 / 集成 | Mixamo 绑定、导出、管线集成 | 规划中 |

关键修复：01 输出前增加最终焊接（`remove_doubles` + 开放边填充），解决 QR xremesh 预处理卡死问题。

## Wrap4D 复刻（Zed/Wrap4D）

逆向复刻 Wrap 2025 的包裹引擎：RBF/相似变换初对齐 → 外层 ICP（重找对应 + 扩半径）→ 内层优化（平滑衰减求解），参数结构对齐官方 Gallery 默认值。含 PyQt GUI、Blender 双向桥接插件与单元测试。

## 环境

- Blender 5.1 + 插件：Quad Remesher、Auto-Rig Pro、Better FBX、MACHIN3tools
- Python 3.11：numpy / scipy / trimesh / MediaPipe（face_landmarker / pose_landmarker）
- Windows，git 大文件走代理推送

## 大资产策略

受 GitHub 100MB 单文件限制，以下资产不入库（已在 `.gitignore` 排除）：ZBrush 工程 `.zpr`、大型 `.bin` 纹理、超大 `.bmp` morph 贴图。本地保留于原路径。
