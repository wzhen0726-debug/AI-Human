# 02QR 独立测试台（2026-10-12 建）

> 目的：在**绝不触碰正式产物**的前提下测试 02 QR 环节（基线复现 / 参数注入 A/B / 失败诊断 / 输入变体）。
> 机制：`02_qr_auto.py` 内置沙箱重定向 `QR_OUT_ROOT` —— 所有【写】产物落 `<QR_OUT_ROOT>/02QR拓扑/...`，输入路径不变（默认吃 01a 当前高模）。本测试台只是给这套机制一个固定入口。

## 速览

| 我要… | 怎么做 |
|---|---|
| 基线复现 | `bash run_qr_sandbox.sh` |
| 注入旋钮 A/B | `QR_SET_FreezeBorders=1 bash run_qr_sandbox.sh` |
| 换输入 | `QR_IN_BLEND="D:/x/xx.blend" bash run_qr_sandbox.sh` |
| 单抽（关重抽） | `QR_DRAW_RETRY=0 bash run_qr_sandbox.sh` |
| 产物在哪 | `沙箱/run_<时间戳>/02QR拓扑/{输出,_中间}/`（每次自动新目录，永不覆盖） |
| 日志在哪 | 各 run 目录内 `run.log` |

> 不设任何环境变量 = 与正式管线**同代码路径**（默认参数与正式跑完全一致）。

## 可调旋钮（全部走环境变量，默认不动）

- **引擎键注入（23 键）**：`QR_SET_<键名>=<值>` —— 含 `FreezeBorders / FollowBorders / MaxQuadRatio / NumPointCirc / DenoiseStrength / VarDensityRatio / SymTopo / MaxNumThread` 等；键名/类型/偏移见
  `E:\WangZhen_Project\AI\ReverseEngineering\QuadRemesher_1.3.0.3452\02_重点分析\清单\参数键_函数级.md`
- 目标面数：`QR_TARGET_QUADS`（默认 150000）；曲率自适应：`QR_ADAPTIVE_SIZE`（默认 95）
- 密度图原型：`QR_DENSITY_MAP=1`（可配 `QR_DENS_R_MM` / `QR_DENS_PLATEAU`）
- 重抽择优：`QR_DRAW_MAX`（默认 3 轮）、`QR_DRAW_RETRY=0` 关闭、`QR_DRAW_STRICT=1` 全坏即失败
- 材质引导（实验）：`QR_USE_MATIDS=1`
- rim 恢复（默认关，用户已否决该路线）：`QR_RIM_RESTORE=1`（不建议）

## 判据口径（与替代方案评估同一套）

跑完与 **QR 基线** 对比。基线数字（150k 档，2026-10-10 留档）：

**161,520 面 / 四边 99.95% / 非流形 0 / 自交对 0 / 边界 86 / 边长均值 3.63mm**

来源：`E:\WangZhen_Project\AI\ReverseEngineering\QuadRemesher_1.3.0.3452\03_运行观察\alt_eval\基线_QR150k.json`

核验要点：四边占比、非流形边(>2 面)、自交对（selfint_clean 口径）、三角总数 ≤350,000、眼窝 rim 折角与侵入（视觉）。

## 约束（重要）

1. **QR 引擎全局串行**：引擎临时目录 `%TEMP%\Exoside\QuadRemesher\Blender` 全局共享 → **不要与正式管线/控制台同时跑**。
2. 单次跑约 5–15 分钟（输入约 193 万面 + 8.x 清理）；开重抽最多 3 轮。
3. 合规口径照旧：本机构建仅用于验证/研究；产品化走采购或自研替代，不涉及授权绕过。
4. 本目录只放测试入口与产物；**不改 `02QR拓扑/scripts/` 和正式 `_中间/输出`**。

## 关联索引

- 管线变更影响核对：`E:\WangZhen_Project\AI\ReverseEngineering\管线变更影响核对_20261012.md`
- QR 逆向首轮结论：`E:\WangZhen_Project\AI\ReverseEngineering\QuadRemesher_1.3.0.3452\04_结论\首轮结论_v1_20261010.md`
- 退出码/失败信号实测：同目录 `退出码与失败信号实测_v1_20261010.md`
- 替代方案评估（QuadWild/QuadriFlow）：`…\03_运行观察\alt_eval\README_产物说明.md`

## 结果记录

测试结论写 `结果/结果_<日期>_<主题>.md`（重要数字附 JSON）；产物留在各自 `沙箱/run_*` 内备查。

## 维护记录

- **2026-10-12 首轮踩坑（已修）**：把 MSYS 形式路径（`/e/...`）当 `QR_OUT_ROOT` 直接传给原生 Blender → 被解析成 `E:\e\...` 怪路径，脚本首存失败退出（**正式产物零影响**；空转证据 `沙箱/run_20261012_155415`）。修复= runner 用 `cygpath -m` 转成 Windows 形式（`E:/...`）再传；探针实测通过后复跑成功（75s）。
- **2026-10-13 按钮 .bat 坑（已修+实测）**：首版 .bat 为 UTF-8+LF，在 cmd 下乱码且行解析碎裂（`'bash.exe' 不是内部或外部命令` 等）。重制为**全 ASCII + CRLF + chcp 65001**（重建器 `工具_重建按钮bat.py`），并**模拟双击实跑验证**：CMDRC=0、无命令级错误、全链路跑通（测试轮 `沙箱/run_20261013_151302`）。