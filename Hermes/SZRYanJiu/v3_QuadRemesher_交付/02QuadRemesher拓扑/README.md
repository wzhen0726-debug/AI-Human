# 步骤02：QuadRemesher 拓扑

**日期**: 2026-07-31  |  **状态**: 已验证通过

---

## 功能

将 01 修复后的高模（193 万三角面）重拓扑为低模（14.9 万四边面），用于后续 UV 展开、纹理烘焙和骨骼绑定。

## 方案

使用 Exoside Quad Remesher（xremesh 引擎）全自动重拓扑。绕过 Blender QR 插件的 modal 算子（在 background 模式下不可用），直接用 Python `subprocess.Popen` 调用 `xremesh.exe`，同步轮询进度文件。

## 流程

1. **加载 01 输出 blend**（01_highpoly_repair.blend）
2. **网格清理（步骤 2.5）**：焊接重复顶点 + 填补孔洞（确保封闭流形，防 xremesh 卡 21%）
3. **导出 FBX** 到 QR 临时目录（inputMesh.fbx）
4. **写 RetopoSettings.txt**（TargetQuadCount=140000，CurvatureAdaptivness=80，SymAxis=X 镜像对称）
5. **subprocess 启动 xremesh.exe**（`cwd=engine_dir` 确保 DLL 加载）
6. **轮询 progress.txt** 直到完成（0~1 进行中，2=完成）
7. **导入 retopo.fbx**，清理原始高模，保存输出

## 关于对称（SymAxis）的决策 — 已关闭

**历史**：02 脚本曾写入 `SymAxis=X` 强制拓扑左右镜像对称，理由是 Mixamo 绑定依赖对称性检测骨骼。

**问题**：当前模型的衣服纹理本身不对称。对称拓扑让左右布线镜像，但纹理仍是原不对称纹理，烘焙后纹理错位。

**结论（用户决策）**：**不使用对称**。自然拓扑跟随原模型几何，纹理正确。Mixamo 对轻微不对称（<5mm）通常也能正常绑定；若后续绑定出现骨骼歪斜，再考虑绑定后手动对称化权重。

**实测**：关闭对称后 QR 输出 141,601 面（左 71,163 / 右 70,092 顶点，自然不对称），283,194 三角面达标，0 非流形。

## 脚本

`scripts/02_qr_auto.py`

## 输入/输出

| 项目 | 路径 |
|------|------|
| 输入 | `01高模修复与黏连检测/models/01_highpoly_repair.blend` |
| 输出 blend | `02QuadRemesher拓扑/02_qr_150k.blend` |
| 输出 FBX | `02QuadRemesher拓扑/02_qr_150k.fbx` |

## 验证结果

| 指标 | 数值 |
|------|------|
| 输入面数 | 1,929,594（三角面） |
| 输出面数 | 146,114 |
| Quad 比例 | 100.0%（146,084 quads + 30 tris） |
| 三角面数 | 292,198（≤30万达标） |
| 非流形边 | 0 |
| 耗时 | 40 秒 |

## 关键前提：输入网格必须封闭流形

xremesh 预处理阶段会修补输入网格的裂缝。若输入含大量未焊接顶点和开放边界（如 7/30 的 172K 重复顶点 + 516K 边界边），修补逻辑会陷入病态计算，卡在 ~21%。

**解决**：01 输出 blend 前必须做 `final_weld_for_qr()`（remove_doubles + edgeloop_fill），确保非流形边 < 50、边界边 < 50。

## 根因分析文档

`问题分析_QR全自动失败.md`（含对照实验、排除假设、最终结论）
