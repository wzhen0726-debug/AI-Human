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
# 开放边界: 统计条数即可(设上限防异常); ⚠ 逐条单边调 edgeloop_fill 是纯无效开销——单边调用恒不建面
#   (算子只在传入边集内走路成环)却每次付 ~250ms 全网格算子开销(实测 347 条=85.7s@1.9M面);
#   真要补孔必须把【整圈边一次性批量传入】(批量会真建面, 属行为改变); 等价证明见 blender-pipeline-bit-exact-speedup
```

## 输入边界环的采样尺度（眼角/尖角乱线的根因）

引擎会把输出环贴着输入边界环采样（偏差 ≤0.04mm），输出边中位长 ≈2.0~2.6mm。
**边界环点距必须与目标边长同尺度：经验 ≈ 目标边长 ×0.25**（目标 ~2mm → 点距 0.5~0.6mm；步长按模型尺度活参数推导，勿写死）。

- 过密（实测 0.22mm/430 点）：一条输出边跨 8~10 个输入点 → 高曲率处（眼角）被近重合点拉扯出
  长直弦/放射扇簇/针状窄面；对照实验：仅把环加密到 0.19mm 即复现乱线，抽稀到 0.55mm 即恢复干净。
- 过稀同样出长直弦（引擎采样素材不足）。
- 尖角处（眼角等）输入环应**留空 ≥3mm**（贴角点会在输出被挤压出窄面/极点）。
- 修复方向：在【生成环的上游侧】把环按 3D 弧长重分组并点回目标点距（并点位置落在原环线上，
  位置偏差 ≤0.04mm）并做眼角留空；位置变化 ≤0.04mm 时视口里几乎看不出——收益全部体现在 QR 输出。
- 下游 QR 侧零改动：修好喂入数据即可，勿加"修复补丁"。

### 眼角形态验收口径（四角各量与「本侧输入环」自比，±9mm 窗口）

| 指标 | 定义 | 实测参考 |
|---|---|---|
| t3max | 窗口内环上最大三点转角 | 修复前最差 83.7° → 修复后 ≤45.5° |
| 针状面 | 面内角 <12° 的面之最长边 | 修复前 2.96mm → 修复后 0 |
| 切角偏差 | 单条输出边跨真值环弧长 ≥1.5mm 时的最大弦偏差 | 修复前 1.47mm → ≤0.28mm |
| 最大环边 | 窗口内最长环边 | 修复前 6.46mm → ≤2.70mm |

- 形态门必须先用**用户目视判过的历史件**标定（用户判差者必须 FAIL）才可用于验收。
- 单轮数值不作数：按 **N≥3 轮中位数**引用（见坑清单 1）。

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

## QR 输出后的缺陷清理（绕向/自交）

QR 把“衣服壳/身体壳”在交界处重拓扑成单层封闭面时，会在衣摆/袖口折边产生**双层近共面微折**
+ **绕向不一致面**（渲染成尖角/台阶/发黑，用户叫“破面”），而边界边/非流形边仍是 0。
实测归属：大腿衣摆 高模=0 → QR=34 → 建碗后=39（QR 产生）；右眼窝外眦 高模=8 → QR=0 → 建碗后=1（建碗产生）。

**在哪一环产生就在哪一环清**：新增 `selfint_clean.py`，在 QR 输出后与建碗后各调一次——
精确自交检测（**不排除共享顶点**，否则判据自盲）→ 质心聚类 → 每簇微焊接（0.8→5mm 取最小清零档）
+ 删同顶点集重复面 + 绕向贪心修复；**守门**：本簇清零 ∧ 非流形/退化不变多 ∧ 不在别处新生簇，否则回退。
实测 51 对 → 0 对、绕向 3 → 0、面数 -0.03%。

完整方法/坑（含审计脚本必须自己 open_mainfile、焊接后索引移位、`ensure_lookup_table`）：
`references/selfint-cleanup-and-defect-audit.md`

## 失败判因：引擎不产错误文本，只有进度与返回码（REA 逆向复核）

- **headless 下失败原因不落任何文件、不进 stdout/stderr**：引擎的错误缓冲由宿主插件注入，只在缓冲非空时才写（反编译实证）。cmdline 直调看到 stdout/stderr 全空是**设计使然**，不是丢日志——别再花时间找日志文件。
- 可用信号 = **`progress.txt`（唯一可靠）**：`2`=成功；**负值=失败，且第二行是给人看的消息**（例 `-1` / `Error: Remeshing failed. (BadInput)`）。**进程退出码恒为 0，成功失败都一样**（4 例实测，含正常件对照组）→ 永远不要用退出码判成败。
- 引擎内部返回值（`XRemesher::DoRetopoFromCmdLine` 反编译）含义：`0x65/101`=输入加载/预处理失败(BadInput、settings 读失败亦同码)、`0x6A/106`=显存不足、`0x12E/302`=试用过期、`0x130/304`=试用需联网、`0x131/305`=BadInput 变体、`0x34/52`=Misc。这些值**不随进程退出码传出**；要按码区分失败类型只能读 `progress.txt` 的消息文本（可含 `(BadInput)` 这类标记）。
- **失败有多快也是判据**：坏输入（缺文件/空网格/单顶点）约 **1.5 秒**即返回且无产出；正常件同样约 1.5s 产出 → 若某轮**挂到硬超时**才被收掉，可先**排除「输入坏」**，往抖动/资源方向查。
- **逐轮抖动与授权/环境无关**：本机这份分发（汉化版）的许可证校验是**构建期关闭**的（总开关硬编码 0；引擎本体不导入任何联网/注册表 API）→ 重抽择优逻辑保留即可，**不要加授权兜底分支**。
- **参数面已到函数级**：36 键的「键 / 结构体偏移 / 类型 / 解析助手」权威表 + 完整调用协议见 REA 工作区 `QuadRemesher_1.3.0.3452/02_重点分析/清单/参数键_函数级.md`；实测确认 **无隐藏键**（ab04 手工清单已穷尽），增量只是类型与偏移。`CurvatureAdaptivness` 是唯一带副作用的键（显式写入会触发重算钩子）。
- **引擎血统与替代评估**：与 ZBrush/Maxon 同源（`MXAutoRetopo*` `/MXCurvatureDirAlgo`/`MXMeshChartsCache`）；`ChSolver.dll` = SuiteSparse CHOLMOD（求解层开源，**壁垒在量化布局算法**）——评「自研替代」时工程量压在布局侧，不在数值求解。
- **开源替代（QuadriFlow / QuadWild-BiMDF）已首轮实测：均未达本节的验证基线**（自交/密度两项硬指标不过，QuadriFlow 另有严格流形闸门）→ 闸门、评测口径、隔离实验方法与实测数字见 `references/alternative-engine-eval.md`；**动手接替代前先读它**，别重踩已排除的路线。
- 完整结论/合规要点/处置选项（采购 vs 替代）见 REA 工作区 `QuadRemesher_1.3.0.3452/04_结论/首轮结论_v1_20261010.md`。

## 坑清单

1. **运行间随机性**：同输入两次运行布线不同——正常（实测甚至 02 级中间件 md5 逐字节相同而角部形态大幅回摆）。**单轮数值不作为验收证据：验收用 N≥3 轮中位数口径**；关键区域质量不要依赖 QR 巧合，用上游修数据/后续重建兜住。
2. **注释≠行为**：脚本里曾出现"只用材质引导"的注释而实际默认关闭——改参数前先读代码，勿信注释。
3. 中文路径可用；settings/temp/输入输出全走绝对路径（原生进程 CWD 可能与 shell 不同）。
4. 100 万+面 FBX 导出/导入较慢属正常；给足超时。
5. **择优落正式**：多轮跑择优后，把【选中轮】产物 cp 到正式路径即可；不要为了"落正式"再跑一轮——会引入新的未受控引擎轮，使择优失效。

## 参考

- 方案md：`方案md记录/v3_QuadRemesher/02QuadRemesher拓扑/`（档案与调研合并版 / QR含眼窝高模重跑记录 / 眼窝碗工序 / QR流程_现状与整理）
- 相关 skill：`blender-digital-human-pipeline`（全链路）、`blender-uv-texture-baking`（QR 后 UV/烘焙）、`blender-pipeline-bit-exact-speedup`（引擎前后处理提速的等价证明）
- AB17 rim 根治实测（环采样尺度/眼角留空/验收口径）：`演示版_终端控制端/logs/_ab17/`（AB17E/F/G/H 报告 + AB17_算法改动说明_20261001.md）
- 替代引擎评测（闸门/评测口径/隔离实验/实测数字）：`references/alternative-engine-eval.md`
