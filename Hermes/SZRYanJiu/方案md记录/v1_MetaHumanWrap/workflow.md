# 高模→低模 头部拓扑自动化 — 技术流程文档

## 1. 项目概述

将 3D 扫描高模人头通过参考打点方式自动化拓扑为 MetaHuman 标准低模，保持低模布线可用于后续绑定和表情动画。

## 2. 输入输出

| 类型 | 文件 | 说明 |
|------|------|------|
| 高模 | `data/high_poly/Scan_Head_Lv5.obj` | 297万顶点，Z-up，面朝-Y，居中后 bbox ±130mm |
| 低模 | `data/low_poly/MH_Head_01.obj` | 8280顶点，MetaHuman拓扑，Z轴零点在脖子(非中心) |
| 特征点 | `data/low_poly/template_landmarks.json` | 21个手动校验的模板顶点索引 |
| MediaPipe | `data/models/face_landmarker.task` | 面部478点检测模型 |
| **输出** | `output/rounds/head_v3.blend` | 贴合结果(含高模+低模) |

## 3. 坐标系差异 (关键!)

| | 扫描 | 模板 |
|---|---|---|
| 鼻尖 | Y=-110mm, Z=-17mm | Y=-111mm, Z=+139mm |
| 下巴 | Z=-122mm (最底) | Z=+61mm |
| 头顶 | Z=+124mm | Z=+283mm |
| Z轴零点 | 几何中心 | 脖子位置 |

**Z轴零点差149mm** — 必须用特征点对齐，不能用质心对齐。

## 4. 管线流程 (fit_v3.py)

```
阶段1: 导入高模 → 居中 → 6方向渲染(512x512, WORKBENCH)
阶段2: MediaPipe 478点检测 → 选最佳视角(-Y, 478点)
阶段3: 2D→3D映射 → 12核心面部点(raycast到扫描表面)
阶段4: 导入低模 → ★特征点Procrustes对齐
   ├── 特征点质心平移 (修正149mm Z轴偏差)
   ├── 特征点距离比缩放 (0.95x)
   └── 再平移修正
阶段5: Shrinkwrap 4轮 (NEAREST_SURFACEPOINT + CorrectiveSmooth)
阶段6: 特征点锚定 25轮 (渐进α=0.3→1.0 + 拉普拉斯平滑)
阶段7: 表面修正 (轻量Shrinkwrap + 重新锚定)
阶段8: 验证 + 保存
```

## 5. 关键参数

| 参数 | 值 | 说明 |
|------|---|------|
| 渲染分辨率 | 512x512 | MediaPipe输入256x256 |
| Shrinkwrap轮数 | 4 | 全NEAREST(不用PROJECT,会导致不对称) |
| CorrectiveSmooth | 2iter/0.15 | 每轮Shrinkwrap后 |
| 锚定迭代 | 25轮 | α=0.3+0.7*(it/24) |
| 拉普拉斯平滑因子 | 0.3 | 非锚点顶点 |
| 表面修正 | 1轮NEAREST + 0.1平滑 | 最终精修 |

## 6. MediaPipe 索引映射

MediaPipe的left/right是图像视角(镜像):
- idx 33 = 图像左侧 = 人物右眼 → right_eye_outer
- idx 263 = 图像右侧 = 人物左眼 → left_eye_outer

## 7. 验证指标

| 指标 | 目标 | v3实测 |
|------|------|--------|
| 12点偏差 | <0.5mm | 0.0mm ✅ |
| 整体均值 | <0.6mm | 0.372mm ✅ |
| <1mm占比 | >95% | 97.1% ✅ |
| 眼对称差 | <3mm | 0.04mm ✅ |
| 嘴对称差 | <3mm | 0.75mm ✅ |

## 8. 已知问题 (待修复)

1. 耳朵: 低模耳朵偏小,Shrinkwrap无法包裹复杂耳廓
2. 上唇: 锚定导致局部扭曲
3. 内眼角: 拉伸变形
4. 鼻翼: 顶点错位
5. 颈部: 边缘锯齿(高模原始问题)

## 9. 运行命令

```bash
"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe" \
  --background --python "scripts/pipeline/fit_v3.py"
```

## 10. 目录结构

```
test01/
├── data/
│   ├── high_poly/     Scan_Head_Lv5.obj (+mtl), Scan_Head_Lv6.glb
│   ├── low_poly/      MH_Head_01.obj (+mtl), template_landmarks.json
│   └── models/        face_landmarker.task
├── scripts/
│   ├── pipeline/      fit_v3.py ★, fit_v2.py, fit_v1.py
│   ├── diagnostics/   diag_*.py
│   └── utils/         render_v3.py, render_verify.py
├── output/
│   ├── rounds/        head_v3.blend, v3_verify/
│   └── legacy_logs/
└── docs/
    ├── workflow.md    本文档
    └── research_report.md  调研报告
```
