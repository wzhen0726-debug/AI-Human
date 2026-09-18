---
name: quadremesher-retopology
description: "Use when QuadRemesher headless 全自动重拓扑: 参数/完成判据/坑。"
version: 1.0.0
author: Hermes Agent
tags: [blender, quadremesher, retopology, headless, 3d, pipeline]
platforms: [windows]
---

# QuadRemesher 全自动重拓扑（QR, headless）

高模（百万级三角）→ 约 15 万 quad（≈30 万三角预算）的低模，供 UV/烘焙/绑定。
对应数字人管线 **02QR拓扑** 环节；权威实现 = `演示版_终端控制端/02QR拓扑/scripts/`（交付镜像 = `v3_QuadRemesher_交付/02QuadRemesher拓扑/`）。

## 引擎直调（关键：modal 算子 headless 不可用）

QR 插件的 modal 算子在 background 模式不可用 → 直接调引擎：

```python
ENGINE = os.path.join(os.environ['APPDATA'], 'Blender Foundation', 'Blender', '5.1',
                      'extensions', 'user_default', 'quadremesher', 'EngineWin', 'xremesh.exe')
# settings 文件写到临时目录; FileIn/FileOut/ProgressFile 用绝对路径
proc = subprocess.Popen([ENGINE, '-s', settingsFile], cwd=os.path.dirname(ENGINE),
                        stdout=open(outF,'w'), stderr=open(errF,'w'))   # 必须重定向到文件!
# 轮询: progress.txt == 2 即完成(插件自身的完成信号); 然后强制收掉进程; 加硬超时兜底
```

- **完成判据 = `progress.txt==2`，不是进程退出**：引擎产出后仍持续跑不退出，`while proc.poll()` 会永久挂起。
- **不要让 stdout/stderr 走 PIPE**：不读会写满管道，引擎在退出前卡住。

## RetopoSettings 参数（经实测选定；换模型可复用）

| 键 | 值 | 说明 |
|----|----|------|
| TargetQuadCount | 150000 | 目标 quad 数；与三角预算换算 ≈ ×2 |
| CurvatureAdaptivness | 95 | 高自适应 |
| ExactQuadCount | 0 | 自适应模式 |
| UseMaterialIds | 0 | 材质边界布线在眼窝处过硬；1 仅作 A/B 实验 |
| UseIndexedNormals | 0 | 取消法向分割 |
| AutoDetectHardEdges | 0 | 取消角度硬边（会抹平眼窝折角） |
| SymAxis | **不写** | 纹理本不对称，强制对称 → 纹理错位；绑定对轻微不对称可容忍 |

## 输入预处理（防卡死）

未焊接顶点 + 开放边界会让引擎卡在 ~21%。导出前必做：

```python
weld_d = max(0.0001, model_h * 0.00006)          # 阈值=模型高×0.00006(不写死)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_d)
# + 对单边边(开放边界)做 edgeloop_fill 补孔(设上限防异常)
```

## QR 输出的后处理（数字人场景）

- **眼孔开放边界 = rim**：沿 rim 重建眼窝碗（深度/环数纯 rim 几何自算，v19）。
- **眼球**是独立对象，在碗重建后摆入并并入；权重在 05 绑定阶段给（顶点组名必须=骨架实际骨名）。
- QR 输出后与高模做对位/质量核验时，**BVH 必须 `BVHTree.FromPolygons`（数据拷贝）**：
  流程中会删高模对象，`FromObject` 引用悬空 → `find_nearest` 大面积返回 None（历史 v53 踩坑）。

## 验证基线

| 指标 | 目标 |
|------|------|
| quad 占比 | ≥99%（≈100%） |
| 非流形边 | 0 |
| 三角面 | ≤预算（本管线 30 万） |
| rim 区面质量 | 不差于同网格皮肤（自参照，见 blender-digital-human-pipeline/references/rim-band-qa.md） |

## 坑清单

1. **运行间随机性**：同输入两次运行 rim 附近布线不同——正常；关键区域质量不要依赖 QR 巧合，用后续重建兜住。
2. **注释≠行为**：脚本里曾出现"只用材质引导"的注释而实际默认关闭——改参数前先读代码，勿信注释。
3. 中文路径可用；settings/temp/输入输出全走绝对路径（原生进程 CWD 可能与 shell 不同）。
4. 100 万+面 FBX 导出/导入较慢属正常；给足超时。

## 参考

- 方案md：`方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/`（档案与调研合并版 / QR含眼窝高模重跑记录 / 眼窝碗工序 / QR流程_现状与整理）
- 相关 skill：`blender-digital-human-pipeline`（全链路）、`blender-uv-texture-baking`（QR 后 UV/烘焙）
