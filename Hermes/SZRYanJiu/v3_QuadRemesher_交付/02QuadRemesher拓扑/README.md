> **2026-09-18 整理**：本目录为 `演示版_终端控制端/02QR拓扑` 的交付镜像（权威实现以演示版为准）。
> 本次整理：脚本同步 ✓ 当前产物镜像到 `_中间/`、`输出/` ✓ 历史实验文件移入 `_归档_历史实验_202608/` ✓
> 清除 5 个 `.blend1` 自动备份 ✓。README 重写为当前真实流程（旧版停留在 2026-07-31 的 140k/对称X 方案 ✗）。

# 步骤02：QuadRemesher 自动拓扑（QR）

**日期**: 2026-08-21 建立 / 2026-09-18 重写  |  **状态**: 已验证通过（全链在跑）

---

## 功能

高模（193 万三角面，含 01a 眼窝空腔 + 眼窝独立材质分区）→ **全自动重拓扑为约 15 万 quad**（≈30 万三角面预算内），
再由碗重建把眼窝补成光滑凹碗，最后并入眼球对象。为 03 UV / 04 烘焙 / 05 绑定提供低模。

## 流程（3 个脚本，控制台 `02` 一条命令全跑）

| # | 脚本 | 作用 |
|---|------|------|
| 1 | `scripts/02_qr_auto.py` | 加载 `01a/_中间/01_1_eye_socket_qr.blend` → 网格清理（焊接+补边界，防盗卡死）→ 导出 FBX → 写 `RetopoSettings.txt` → Popen 启动 `xremesh.exe` → 轮询 progress → 导入 retopo.fbx → 保存 |
| 2 | `scripts/02qr_socket_cup.py` | 沿 QR 输出的眼孔开放边界（=rim）重建眼窝碗（v19：深度/环数纯 rim 几何自算） |
| 3 | `01a/scripts/run_eyeball_v2.py` | 眼球摆入并并入（解剖规律定位，见 01A 文档） |

## 引擎调用（headless 关键）

- QR 插件的 modal 算子在 background 模式**不可用** → 直接调引擎：
  `%APPDATA%/Blender Foundation/Blender/5.1/extensions/user_default/quadremesher/EngineWin/xremesh.exe -s RetopoSettings.txt`
- **完成判据是 `progress.txt == 2`，不是进程退出**（引擎产出后仍持续跑不退出）。
  做法：① stdout/stderr 重定向到文件（PIPE 不读会写满卡死） ② progress==2 即收进程 ③ 硬超时兜底。

## RetopoSettings（当前权威值，全部经实测选定）

| 键 | 值 | 说明 |
|----|----|------|
| TargetQuadCount | 150000 | 对应三角 ≈30 万，预算内 |
| CurvatureAdaptivness | 95 | 高自适应，细节处加密 |
| ExactQuadCount | 0 | 自适应模式 |
| UseVertexColorMap | 0 | — |
| UseMaterialIds | 0（默认） | 材质边界布线在眼窝处过硬，实测该组最优；`QR_USE_MATIDS=1` 仅实验开关 |
| UseIndexedNormals | 0 | 取消法向分割 |
| AutoDetectHardEdges | 0 | 取消角度检测硬边（曾抹平眼窝折角 35.7°） |
| SymAxis | 不写 | 纹理本不对称，强制对称拓扑会导致纹理错位 |

## 关键前提与坑

1. **输入必须封闭流形**：未焊接顶点 + 开放边界会让 xremesh 卡 ~21%（历史 172K 重复顶点 + 516K 边界边）。
   `02_qr_auto.py` 内置自适应焊接（阈值 = 模型高 × 0.00006）+ 边界填补，01 输出另做 `final_weld_for_qr()` 兜底。
2. **BVH 必须 `FromPolygons`（数据拷贝）**：脚本 8.5 步会删高模对象，`FromObject` 引用悬空 → `find_nearest` 大面积返回 None。
3. **每次运行拓扑略有随机**：同输入重跑 rim 附近布线不同（正常），rim 区质量由 02qr_socket_cup 的碗重建兜住。
4. 中文路径可用；`UseMaterialIds` 等 env 开关仅实验。

## 输入 / 输出（当前路径）

| 项目 | 路径 |
|------|------|
| 输入 | `演示版_终端控制端/01a眼窝眼球/_中间/01_1_eye_socket_qr.blend` |
| QR 中间 | `02QR拓扑/_中间/02_qr_150k.blend`、`02QR输入_眼窝材质分区_高模.blend` |
| 输出 | `02QR拓扑/输出/02_qr_150k_socket.blend`（主产物）、`02_qr_150k_未补洞_拓扑后.blend`、`02_qr_150k.fbx` |

## 验证（最近一次全链实测）

15 万 quad 级 / 非流形 0 / 眼窝碗逐环与参考均差 ≤0.07mm / rim 区坏面占比与皮肤相当（见 01A rim 自适应修复记录）。

## 参考文档（方案md记录）

- `方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/QuadRemesher档案与调研_合并版.md`
- `方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/QR含眼窝高模重跑记录_20260821.md`
- `方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/眼窝碗工序_问题与方案_20260917.md`
- `方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/QR流程_现状与整理_20260918.md`
- 本目录 `rim问题_技术备忘录.md`（历史）、`_归档_历史实验_202608/`（rim 系列实验与日志，只读）
