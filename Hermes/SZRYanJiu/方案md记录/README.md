# 方案md记录 — 文件夹索引

> 最后更新: 2026-07-29

## 目录结构

```
方案md记录/
├── README.md                          ← 本文件
│
├── v1_MetaHumanWrap/                  ← MetaHuman 头部/身体 Wrap 方案
│   ├── MetaHumanWrap_完整档案.md      ← 头部 wrap v3.4 完整技术档案（❌ 数值达标但视觉质量差，不可用）
│   ├── Body_Wrap方案失败记录.md       ← 身体 wrap 全部失败记录（❌ 已放弃）
│   ├── research_report.md             ← 行业调研报告（Wrap4D/Faceform等）
│   ├── workflow.md                    ← fit_v3.py 技术流程文档
│   ├── fit_v3.py                      ← 头部 wrap 核心脚本
│   └── data_low_poly/                 ← 模板 landmark 数据
│
├── v2_镜像对称/                       ← 镜像对称方案（独立模块）
│   ├── 镜像对称测试_完整档案.md       ← 完整技术档案
│   ├── 镜像测试报告.md                ← 测试报告
│   ├── Gemini顾问_RANSAC谱匹配.md    ← 外部顾问意见
│   ├── Gemini顾问_破局方案.md         ← 外部顾问意见
│   └── zbrush智能对称调研.md          ← ZBrush 对称功能调研
│
├── v4_前瞻性技术方案/               ← 三阶段演进路线（MVP→分割+ARAP→SMPL-X）
│   └── 三阶段演进路线.md             ← 核心文档：当前MVP→未来工业级管线
│
├── v3_QuadRemesher/                   ← QR 降面全流程方案（主方案）
│   ├── _方案与WBS/                    ← 总体技术方案和 WBS
│   │   ├── 技术方案_全自动化版v3.md   ← 全自动化管线方案
│   │   ├── 项目WBS_全自动化版v3.md   ← 项目 WBS
│   │   └── 简化版方案缺陷分析.md      ← 简化版方案的风险分析
│   ├── 01高模修复与黏连检测/           ← 高模几何修复
│   ├── 02QuadRemesher拓扑/            ← QR 降面方案
│   ├── 03自动UV/                      ← UV 展开方案（含 UV 调研报告）
│   ├── 05骨骼绑定/                    ← Mixamo 骨骼绑定方案
│   ├── 拓扑传递行业调研_子代理报告.md ← wrap/retopology 行业调研
│   └── 高模到低模拓扑传递与UV展开_完整调研档案.md ← 综合调研档案
│
└── [已归档/已移动]
    v3_MixamoSkeleton_骨骼绑定方案.md → v3_QuadRemesher/05骨骼绑定/Mixamo骨骼绑定方案.md
```

## 版本演进

| 版本 | 方案 | 状态 | 说明 |
|------|------|------|------|
| v1 | MetaHuman Wrap | ❌ 不可用 | 头部v3.4数值达标(0.402mm)但视觉质量差(耳朵/嘴唇/眼角扭曲)，身体因衣服嵌套全部失败 |
| v2 | 镜像对称 | 参考 | 独立模块，不依赖wrap |
| v3 | QR降面+自动UV | 进行中 | 主方案，wrap路线已放弃 |
| v4 | 三阶段演进路线 | 规划 | MVP→3D分割+ARAP→SMPL-X，见 `v4_前瞻性技术方案/` |

## 关键结论

1. **头部 wrap (v3.4)**: MediaPipe 478点 + Procrustes + Shrinkwrap 4轮 + 锚定迭代 25轮 → 数值0.402mm/96.2%，但耳朵偏小/上唇扭曲/内眼角拉伸/鼻翼错位/颈部锯齿，**视觉质量不可用**
2. **身体 wrap**: ❌ 已放弃 — 根因是 Tripo AI 高模含衣服嵌套 + 53.1% 法线反转，所有自动方法失效
3. **UV 展开**: QR 均匀 quad 网格 UV 展开质量差(≤4.5/10)，所有自动方案（Blender/RizomUV/xatlas）碎片化严重
4. **骨骼绑定**: 使用 Mixamo 标准（不用 Auto-Rig Pro），通过几何分析自动检测关节位置
