# Quad Remesher Headless (Background) Execution — xremesh.exe Direct Call

> Verified 2026-07-29 on Blender 5.1 + Quad Remesher Bridge 1.3.2 (汉化版 GJJ).
> QR produced 86,542 quads from a 1.93M-face Tripo high-poly in ~90 seconds.

## Problem: `bpy.ops.qremesher.remesh()` cannot run in `--background`

`QREMESHER_OT_remesh.execute()` returns `{'RUNNING_MODAL'}` and relies on
`context.window_manager.event_timer_add(0.3, window=context.window)` +
`modal_handler_add(self)`. In `--background` mode there is no window, so the
operator is cancelled immediately (`cancel called!!!` in console) after only
exporting the input FBX — no remeshing ever happens.

## Addon enable quirk

```python
import addon_utils
try:
    addon_utils.enable('bl_ext.user_default.quadremesher')
except KeyError:
    pass  # KeyError is EXPECTED — operators + scene.qremesher register anyway
```

- `'quadremesher'` (short name) fails with "No module named 'quadremesher'".
- `'bl_ext.user_default.quadremesher'` raises `KeyError: bpy_prop_collection[key]`
  from its own register() UI code, BUT `bpy.ops.qremesher.remesh` and
  `bpy.context.scene.qremesher` are both registered and usable. Catch and continue.

## Solution: call `xremesh.exe` directly via subprocess

QR's operator is just a wrapper around an external engine. You can drive it
yourself in 3 steps:

### 1. Export the high-poly as FBX to the QR temp dir

```python
import os, tempfile
QR_TEMP = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")
os.makedirs(QR_TEMP, exist_ok=True)
input_fbx = os.path.join(QR_TEMP, "inputMesh.fbx")

bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
bpy.context.view_layer.objects.active = high_poly
bpy.ops.export_scene.fbx(filepath=input_fbx, use_selection=True,
                         use_mesh_modifiers=False, mesh_smooth_type='OFF',
                         bake_anim=False, path_mode='AUTO')
```

### 2. Write RetopoSettings.txt

```python
settings_file = os.path.join(QR_TEMP, "RetopoSettings.txt")
retopo_fbx    = os.path.join(QR_TEMP, "retopo.fbx")
progress_file = os.path.join(QR_TEMP, "progress.txt")

# Remove stale outputs so the wait-loop doesn't exit early
for f in (retopo_fbx, progress_file):
    if os.path.exists(f): os.remove(f)

with open(settings_file, 'w') as f:
    f.write('HostApp=Blender\n')
    f.write(f'FileIn="{input_fbx}"\n')
    f.write(f'FileOut="{retopo_fbx}"\n')
    f.write(f'ProgressFile="{progress_file}"\n')
    f.write('TargetQuadCount=140000\n')     # Adjust to hit ≤300K triangles. 1 quad ≈ 2 tris.
    f.write('CurvatureAdaptivness=80\n')      # 0-100, higher = denser quads in high-curvature areas
    f.write('ExactQuadCount=0\n')              # 0 = adapt_quad_count True
    f.write('UseVertexColorMap=0\n')
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\\n')
    # SymAxis=XYZ + SymLocal=1  if symmetry needed — SEE WARNING BELOW before enabling
```

### 3. Launch xremesh.exe and poll for retopo.fbx

**CRITICAL**: Set `cwd=engine_dir` so xremesh can find its DLLs (`xremeshlib.dll`,
`Qt5Core.dll`, etc). Without this, the engine may start but fail to compute.

```python
import subprocess, time
QR_ENGINE = r"C:\Users\<user>\AppData\Roaming\Blender Foundation\Blender\5.1\extensions\user_default\quadremesher\EngineWin\xremesh.exe"
engine_dir = os.path.dirname(QR_ENGINE)

# 输出落盘, 绝不用 stdout=PIPE 而不读 —— 管道写满会让引擎在退出前卡住,
# 而脚本又是 while proc.poll() 死等退出信号 → 永久挂起(实测卡 15min、CPU 只走了 23s,
# 但 retopo.fbx + progress.txt=2 早已写好)。输出落盘还能留引擎警告供排查。
_out = open(os.path.join(QR_TEMP, "xremesh_stdout.txt"), "w", encoding="utf-8", errors="replace")
_err = open(os.path.join(QR_TEMP, "xremesh_stderr.txt"), "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([QR_ENGINE, "-s", settings_file],
                        cwd=engine_dir,  # CRITICAL: ensures DLL loading
                        stdout=_out, stderr=_err)

# 完成判据 = progress.txt == 2 (插件自身就是这样判的: qr_operators.py modal 里 ProgressValueFloat==2 → doRemeshing_Finish),
# 不是进程退出也不是 progress==1.0。
start, timeout = time.time(), 1800
while True:
    if proc.poll() is not None:
        break
    time.sleep(2)
    val = None
    if os.path.exists(progress_file):
        lines = open(progress_file).read().splitlines()
        if lines:
            try:
                val = float(lines[0])
            except ValueError:
                val = None
            if val is not None and val < 0:
                print("xremesh ERROR:", lines[1] if len(lines) > 1 else val)
    if val == 2 and os.path.exists(retopo_fbx):
        break
    if time.time() - start > timeout:
        print("xremesh 超时")
        break
if proc.poll() is None:      # 引擎常驻不退 → 收掉进程继续(结果已落盘)
    proc.kill()
    try: proc.wait(timeout=20)
    except Exception: pass
_out.close(); _err.close()
```

### 4. Import the result

```python
bpy.ops.import_scene.fbx(filepath=retopo_fbx)
qr_obj = bpy.context.active_object
# Name comes in as "Retopo_<original_name>" — select by that prefix, NOT by
# face count, because the high-poly is still in the scene.
```

## Pitfalls

- **Do NOT identify the QR output by "lowest face count" alone if other low-poly
  objects may exist** — QR names its output `Retopo_<inputname>`. Filter on the
  `Retopo_` prefix first, fall back to face count.
- **xremesh.exe needs VC++ runtimes** — the EngineWin folder ships
  `Windows_Patch_vcredist_x64.exe`; QR's modal operator auto-launches it after
  20s of no progress file. In headless mode, if no `progress.txt` appears within
  ~20s, install the redist manually.
- **The progress file lags** — it may sit at 0.96 for a long while at the end;
  `progress==1.0` never appears. 完成信号是 `progress.txt == 2`(插件同判据), 且那时 retopo.fbx 已落地。
- **引擎产出结果后可能常驻不退**: 实测 retopo.fbx 已写好 5 秒后引擎仍在跑(CPU 还涨)。
  脚本若等“进程退出”就永远等不到 — 用 `progress==2` 判完成并主动 kill 引擎。
- **驱动脚本的输出目录**: 测试期 QR 产物写本 stage 的 `02QR拓扑/输出/`(GUI 核验处), 不写 `交付/`; 约定与路径改法见 `working-conventions.md`。
- **Result deviation & triangle ceiling**: TargetQuadCount=140000 produced 134,674 quads (269,334 triangles) on a resized (1.81m) Tripo model. **Always verify `quads*2+tris ≤ 300000`** — the user's ceiling is 30万三角面 (Mixamo safe limit). If the model was resized/scaled, QR allocates more faces — tune TargetQuadCount down accordingly. ExactQuadCount=0 (adaptive) is recommended; exact mode is slower and less robust. **Tuning history**: 250000→470K tri (too many), 150000→307K tri (still over on resized model), 140000→269K tri (correct).

- **ZED camera conflict (2026-07-30)**: ZED.exe blocks xremesh startup — kill ZED before QR (`taskkill /F /T /IM Zed.exe`). ZED auto-restarts; kill repeatedly during long runs. See `zed-camera-xremesh-conflict.md`.
- **串行铁律：同一时刻只跑一个 QR 实例**——引擎共用全局临时目录（QRTemp），并行跑会互踩串产物（产物混轮次、面数对不上，污染会一路带进下游交付）；跑前确认无其它 blender/QR 进程。
- **QR 的临时/工作目录必须纯 ASCII**：原生 xremesh.exe 对非 ASCII 路径不稳（实测在中文 temp 目录下秒级 `BadInput`；同一份 FBX 走 ASCII 目录即正常）——settings/FileIn/FileOut 都落在一个私有 ASCII temp 目录里，别直接复用全局 QRTemp（官方链路平安是因为其 QRTemp 在 `%TEMP%` 的 ASCII 路径）。

- **~~Hermes/background-session stall at ~21% (2026-07-30)~~** — **DISPROVEN (2026-07-31)**: The ~21% stall is caused by **input mesh fragmentation** (unwelded duplicate vertices + open boundary edges), NOT by Qt/session/window-station issues. `subprocess.Popen([engine, "-s", settings], cwd=engine_dir)` works perfectly from Hermes `--background` Blender. The same engine, same session, same settings succeeds when given a clean (welded) mesh. The earlier "Qt GUI needs interactive session" hypothesis was wrong — xremesh's batch path (`-s` flag) does not depend on interactive Window Station. **Correct fix**: always weld the mesh before exporting FBX (see next bullet).

- **Input mesh fragmentation deadlock (2026-07-31)**: If xremesh stalls at ~21% even in an interactive session, the root cause is a **fragmented input mesh** (unwelded duplicate vertices + open boundary edges). xremesh's preprocessing tries to stitch the fragments and enters pathological computation. Diagnosis: `remove_doubles` on the source mesh reports hundreds of thousands of merged verts; `is_manifold` edges equal boundary edges. Fix: weld vertices (`bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)`) and fill residual holes (`edgeloop_fill`) before exporting FBX. Verified: 172,285 welded verts / 516,960 boundary edges → 11 boundary edges, QR completes in 90s. See `qr-input-mesh-welding.md`.

- **SymAxis=X symmetric retopo breaks asymmetric textures (2026-08-01, user decision)**: Writing `SymAxis=X` forces the QR output to be perfectly L/R mirrored (verified: 70,732 = 70,732 verts per side, 100% symmetric). The stated reason was "Mixamo auto-rig detects bones better on symmetric meshes". **But if the source model's clothing texture is itself asymmetric, mirrored topology + original asymmetric texture = misaligned bake.** The mirrored quads sample UV positions designed for the unmirrored layout. User rejected the result: "我不需要对称啊，对称后的纹理都不对了". **Default to NO SymAxis for AI-generated models with real textures.** Mixamo tolerates <5mm asymmetry fine (71,163 vs 70,092 verts post-QR is harmless). If bone placement comes out lopsided later, symmetrize the WEIGHTS after binding instead of the topology before it. See `qr-symmetry-decision.md`.

- **Local geometric anomaly repair pitfalls (2026-08-03)**: Chest/belly bump/dent repair using XZ-projection reference planes caused symmetric double pits. Correct approach: 3D Euclidean distance reference, diagnose before repair, verify vs original model. See `local-geometric-anomaly-repair.md`.

## 与 01a 眼窝流程的接缝: boolean 流程下"材质引导"不可用

01a 换成棱柱 boolean 开洞后, 眼窝 = **真正的空腔**(边界环是开放边, 洞内没有碗面), 而 02 驱动脚本
是为旧 cup 流程写的(依赖 `v44tag_L/R` 碗面标记 + EyeSocket 材质分区引导 QR 沿 rim 布线)。后果与对策:
- `assign_socket_material.py` 的 tag 依赖会直接断言失败 → 已加**几何回退**: 无 tag 时按
  "面心在 rim 环 XZ 多边形内 + 深度窗口" 找眼窝面; 空腔型找不到内侧面(结果为 0)→ 打日志跳过材质分区,
  仍生成 `_qr.blend` 副本(保持 02 的输入文件契约)。
- 02 脚本里所有"材质引导"相关断言(碗面 tag / 材质槽数 ≥2 / rim 内外真值缓存)都要按 `QR_USE_MATIDS` **条件化**:
  关掉时打印提示并继续, 不再 raise。
- 参数: 空腔流程用 `UseMaterialIds=0`; 用户人工验证过的一组 = TargetQuadCount 150000 / CurvatureAdaptivness 95 /
  UseMaterialIds 0 / AutoDetectHardEdges 0 / 不写 SymAxis。实测 161,009 面(quad 99.996%、非流形 0) =
  **322,012 tris, 超 30 万上限**; 要守上限用 140000(≈289k tris)。差异只在"上限是否豁免", 让用户选。
- 期望输出形态(验收): 眼孔保留为**闭合边界环**(实测 L 39 / R 47 点, 段长中位 1.9~2.2mm);
  孔缘 3 圈内四边面长宽比中位 ~1.4、超 3 的 0 个; 非流形边 0。
- 改了 02 驱动脚本后**先实跑一遍再谈结果**: 变量定义可能在历次编辑中丢失(只留引用处)而脚本 exit 0。
- **QR 之后的低模眼窝碗重建**（在低模上给眼孔补碗面, 眼球坐进去）见 `qr-lowpoly-eye-socket.md`（现行完整做法；`post-qr-socket-bowl.md` 已改为指向它）。

## 引擎能力边界与隐藏旋钮（实测；这些硬试没用）

枚举键：dump `xremeshlib.dll` 字符串块（引擎侧）+ `qr_operators.py`（插件写盘 11 键）/`__init__.py`（面板）。手写注入通道：settings 文件内 `QR_SET_<键>=<值>`（本管线环境变量）。

- **开放边界采样与全局面尺寸硬耦合**：没有“只在局部细分”的旋钮。`FreezeBorders=1`（+Coef）是唯一能锁真值边界的键，但边界点距会被当成全局面尺寸目标——0.22mm 的精细边界 → ~4770 万面（预算 295×）、导入 24 分钟不完；边界先粗化到 ~1mm 再冻结 → 3 秒 `Remeshing failed (BadInput)`（FreezeBorders=0 对照同错）。「锁边界」与「压预算」不可兼得。
- **顶点色密度图只影响内部**：官方画笔上限 ×4（`painted_quad_density ∈ [0.25,4.0]`；红=(1,1-n,1-n)/青=(1+n,1,1)；`UseVertexColorMap=1` + `QR_SET_VarDensityRatio=4`）。实测（r=10mm、plateau 0.5）眼周 4mm 带 100% 四边、0 扇/0 n-gon、全模面数持平，但**边界只弱响应**（rim 边长中位 2.166→1.956 / 1.762→1.780mm、转角 max 68.7→44.1 / 83.1→53.0°）。
- **面数换锐度不划算**：全模 ~604k（TargetQuadCount 650k）时 rim 才到 1.08/1.35mm，仍解决不了内眼角（≈50.7°），且眼周细长面 49/31（≈10×）、极点 364→500。
- **比目标四边尺寸更细的特征解析不了**：眼角 3D 曲率半径 ~2.1mm < 眼周目标边长 2.4mm 时引擎在该处拥挤/碎片/自交——修法在**输入侧**（倒圆/带行重建），见 `qr-input-crowding.md`。
- **面板未暴露可注入键**：TargetEdgeLength、TargetQuadCountAsInputPercentage、FreezeBorders(-Coef)、FollowBorders、VarDensityRatio、NumPointCirc、MaxQuadRatio、DenoiseStrength、UsePolygonGroups、UseSmoothingGroups、UseHardEdgeFlags、UseFacesSelections、UseEdgesSelections、AutoDetectHardEdges_Angle、SymTopo、MaxNumThread、PreProcess_WeldPoints、PostProcess_SplitPointsOnCreasedNormals 等；引擎与 ZBrush ZRemesher 同源。**无 Guides/Curves** → 曲线/边引导此版本不可用。
- **运行间非确定**：同输入两跑，面数/边界采样点（实测 50 vs 31）/自交对数（0 vs 5）/原始输出翻转面数（实测 0 ↔ 70 万+）都不同——验收要连跑两次并给出差异（先跑基线两次定噪声，实测两跑差 60%），单次运行不构成证据。
- **跑次比选（本轮制）**：原始翻转面数抽风的轮次直接弃用留档，采用“成品全网格面朝向体检=0”的合格轮；自交清理有不收敛轮（连跑数轮仍残留数对，集中背部）——不在验收门内的残留靠换轮绕开，别无限掷轮；在门内的（眼角盒严格口径）不合格必须换轮。日志翻转计数只是触发器，判生死看成品体检（`blender-face-orientation-audit` 及其脚本）。

## Working script

A complete runnable implementation lives in the project at
`test02/mvp_pipeline/scripts/02_qr_remesh.py` (loads high-poly blend → FBX →
settings → xremesh → import → save).

> Related: `script-file-health-audit.md` — if the QR driver script "errors out" before
> ever reaching xremesh (SyntaxError at import, read_file shows it as binary), check for
> file-encoding corruption first; the logic is fine.
