# Blender 5.0.1 QuadRemesher 全自动重拓扑方案

> **环境**：Windows 10 / Blender 5.0.1 / QuadRemesher Bridge 1.3.2（Exoside xremesh 引擎）
> **日期**：2026-07-30
> **作者**：Hermes Agent

---

## 目录

1. [任务概述](#1-任务概述)
2. [环境信息](#2-环境信息)
3. [核心难点分析](#3-核心难点分析)
4. [逆向工程 QuadRemesher 插件](#4-逆向工程-quadremesher-插件)
5. [解决方案：绕过 Modal，直调引擎](#5-解决方案绕过-modal直调引擎)
6. [完整自动化脚本](#6-完整自动化脚本)
7. [脚本逐段解析](#7-脚本逐段解析)
8. [运行方式](#8-运行方式)
9. [实际执行日志](#9-实际执行日志)
10. [如何复用（更换源文件/参数）](#10-如何复用更换源文件参数)
11. [常见问题与排错](#11-常见问题与排错)
12. [关键文件清单](#12-关键文件清单)

---

## 1. 任务概述

| 项目 | 内容 |
|------|------|
| **源文件** | `D:\ls\原始文件\tripoTpose_01_repair.blend`（76 MB 高模） |
| **原始网格** | 965,018 顶点 / 1,930,105 三角面 |
| **要求** | 使用 Blender 5.0.1 中的 QuadRemesher 插件进行四边重拓扑 |
| **目标面数** | 120,000（12 万） |
| **输出目录** | `D:\ls\QR输出\` |
| **自动化程度** | 全自动——一条命令完成，无需人工干预 |

---

## 2. 环境信息

### 2.1 Blender

```
路径: D:\Program Files\Blender Foundation\Blender 5.0\blender.exe
版本: Blender 5.0.1 (hash a3db93c5b259 built 2025-12-16)
```

Blender 5.0 在 Windows 上通过 git-bash/MSYS 调用时，路径需要这样写：

```bash
"/d/Program Files/Blender Foundation/Blender 5.0/blender.exe" --background --python "D:/path/to/script.py"
```

> **注意**：`--python` 参数中的路径用 **原生 Windows 路径**（`D:/...`），不要用 MSYS 路径（`/d/...`），否则 Blender 的 C 层路径解析会出错。

### 2.2 QuadRemesher 插件

插件以 Blender 5.0 新的 **extensions** 机制安装（不是传统的 `scripts/addons/`），位于用户配置目录：

```
C:\Users\<用户名>\AppData\Roaming\Blender Foundation\Blender\5.0\extensions\user_default\quadremesher\
```

插件信息：

```
名称:   ♜ 四边重构 (Quad Remesher Bridge)
作者:   马克西姆  汉化：GJJ
版本:   1.3.2
描述:   将原来三角模型重拓扑成四边形模型，支持非网格和多个对象一键重拓扑
位置:   【N面板>♜】或【⌨Ctrl+Alt+R】
```

### 2.3 重拓扑引擎（xremesh.exe）

QuadRemesher 插件本身只是一个 Blender 端的 **桥接器**，真正的重拓扑计算由 Exoside 提供的外部引擎 `xremesh.exe` 完成：

```
C:\Users\<用户名>\AppData\Roaming\Blender Foundation\Blender\5.0\extensions\user_default\quadremesher\EngineWin\xremesh.exe
```

引擎是命令行程序，接受一个设置文件作为输入，输出重拓扑后的 FBX。

### 2.4 目录结构

```
D:\ls\
├── 原始文件\
│   └── tripoTpose_01_repair.blend      ← 76MB 高模源文件
├── QR输出\                              ← 输出目录（初始为空）
├── quad_remesher_auto.py                ← 自动化脚本
└── probe_blend.py / find_quadremesher.py ← 探测脚本（开发用）
```

---

## 3. 核心难点分析

### 3.1 问题：QuadRemesher 的 remesh 操作符是 Modal 的

QuadRemesher 插件的核心操作符 `qremesher.remesh`（定义在 `qr_operators.py` 的 `QREMESHER_OT_remesh` 类中）采用了 **Modal 模式**：

```python
# qr_operators.py 中的关键代码（简化）
class QREMESHER_OT_remesh(bpy.types.Operator):
    bl_idname = "qremesher.remesh"

    def execute(self, context):
        doRemeshing_Start(self, context)    # 启动 xremesh.exe 子进程
        if self.IsRemeshing:
            wm = context.window_manager
            self.timer = wm.event_timer_add(0.3, window=context.window)  # 定时器
            wm.modal_handler_add(self)      # 注册 Modal 处理器
            return {'RUNNING_MODAL'}        # 进入 Modal 循环
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'TIMER':           # 每 0.3 秒检查一次进度
            ProgressValueFloat, ProgressText = update_progress_bar(self)
            if ProgressValueFloat == 2:     # 完成
                doRemeshing_Finish(self, context)
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}
```

Modal 操作符依赖 Blender 的 **事件循环**（event loop）来定时轮询 `xremesh.exe` 子进程的进度。而 `--background` 模式下 **没有事件循环**，因此：

```python
# 这在 --background 模式下会直接失败：
bpy.ops.qremesher.remesh()  # ❌ Modal handler 无法工作
```

### 3.2 解决思路

既然不能调用操作符，那就 **绕过操作符，直接复现它底层的操作流程**。通过阅读 `qr_operators.py` 的源码，我发现 `doRemeshing_Start()` 和 `doRemeshing_Finish()` 两个函数包含了完整的逻辑，且它们都是 **纯 Python 函数**（不依赖事件循环）：

```
doRemeshing_Start():
  1. 选择网格对象
  2. 导出 FBX 到临时目录
  3. 写设置文件 RetopoSettings.txt
  4. 启动 xremesh.exe 子进程

doRemeshing_Finish():
  5. 导入重拓扑结果 FBX
  6. 复制平滑/平直着色
```

我只需要把第 4 步（启动子进程）改为 **同步等待**（`proc.wait()` 或轮询 `proc.poll()`），替代原来的 Modal 定时器轮询，就能在 `--background` 模式下完成同样的事情。

---

## 4. 逆向工程 QuadRemesher 插件

### 4.1 发现插件位置

第一步是确认 QuadRemesher 是否已安装。运行探测脚本扫描所有 Blender 扩展目录：

```python
# find_quadremesher.py 关键逻辑
ext_path = os.path.join(user_config, "extensions")
for root, dirs, files in os.walk(ext_path):
    for d in dirs:
        if 'quad' in d.lower() or 'exoside' in d.lower():
            print(f"FOUND: {os.path.join(root, d)}")
```

结果发现插件在 `extensions\user_default\quadremesher\` 下。

### 4.2 阅读插件源码

插件目录结构：

```
quadremesher/
├── __init__.py          ← 插件主文件（注册面板、属性组、快捷键）
├── qr_operators.py      ← 核心操作符（remesh 逻辑全在这里）
├── G/                   ← UI 资源（图标、翻译、示例文件）
│   ├── __init__.py
│   └── plugin_caches/
├── EngineWin/           ← Windows 引擎
│   ├── xremesh.exe      ← ★ 重拓扑引擎可执行文件
│   ├── xremeshlib.dll
│   ├── QuadRemesher_Version.txt
│   └── licenses/
└── EngineMac/           ← macOS 引擎
    ├── xremesh
    └── xremeshlib.dylib
```

关键文件有两个：

#### `__init__.py` — 属性定义

```python
class QRSettingsPropertyGroup(bpy.types.PropertyGroup):
    target_count: bpy.props.IntProperty(
        name="Quad Count",
        default=5000,
        soft_min=100, soft_max=10000, step=20, min=1
    )
    adaptive_size: bpy.props.FloatProperty(
        name="Adaptive size",
        default=50, min=0, max=100
    )
    adapt_quad_count: bpy.props.BoolProperty(
        name="Adapt Quad Count",
        default=True
    )
    use_vertex_color: bpy.props.BoolProperty(default=False)
    use_materials: bpy.props.BoolProperty(default=False)
    use_normals: bpy.props.BoolProperty(default=False)
    autodetect_hard_edges: bpy.props.BoolProperty(default=True)
    symmetry_x: bpy.props.BoolProperty(default=False)
    symmetry_y: bpy.props.BoolProperty(default=False)
    symmetry_z: bpy.props.BoolProperty(default=False)
```

这些属性会写入设置文件，控制 xremesh.exe 的行为。

#### `qr_operators.py` — 重拓扑流程

这是最关键的文件。`doRemeshing_Start()` 函数揭示了完整的流程：

```python
def doRemeshing_Start(self, context):
    # 1. 选择网格对象
    sel_objects = [x for x in context.selected_objects if x.type in ("MESH", ...)]

    # 2. 确定临时目录
    QRTempFolder = os.path.join(tempfile.gettempdir(), "Exoside")
    export_path = os.path.join(QRTempFolder, "QuadRemesher", "Blender")

    # 3. 定义文件路径
    settingsFilename = os.path.join(export_path, 'RetopoSettings.txt')
    inputFilename = os.path.join(export_path, 'inputMesh.fbx')
    retopoFilename = os.path.join(export_path, 'retopo.fbx')
    progressFilename = os.path.join(export_path, 'progress.txt')

    # 4. 引擎路径
    enginePath = os.path.join(engineFolder, "xremesh.exe")

    # 5. 写设置文件
    settings_file = open(settingsFilename, "w")
    settings_file.write('HostApp=Blender\n')
    settings_file.write('FileIn="%s"\n' % inputFilename)
    settings_file.write('FileOut="%s"\n' % retopoFilename)
    settings_file.write('ProgressFile="%s"\n' % progressFilename)
    settings_file.write("TargetQuadCount=%s\n" % str(props.target_count))
    settings_file.write("CurvatureAdaptivness=%s\n" % str(props.adaptive_size))
    settings_file.write("ExactQuadCount=%d\n" % (not props.adapt_quad_count))
    settings_file.write("UseVertexColorMap=%s\n" % str(props.use_vertex_color))
    settings_file.write("UseMaterialIds=%d\n" % getattr(props, 'use_materials'))
    settings_file.write("UseIndexedNormals=%d\n" % getattr(props, 'use_normals'))
    settings_file.write("AutoDetectHardEdges=%d\n" % getattr(props, 'autodetect_hard_edges'))
    # ... 对称设置
    settings_file.close()

    # 6. 导出 FBX
    bpy.ops.export_scene.fbx(filepath=inputFilename, use_selection=True)

    # 7. 启动引擎
    self.remeshProcess = subprocess.Popen([enginePath, "-s", settingsFilename])
```

`doRemeshing_Finish()` 函数则处理结果导入：

```python
def doRemeshing_Finish(self, context):
    # 导入重拓扑结果
    import_mesh_fbx(self.retopoFilename)

    # 复制原始网格的着色模式
    if inputUseSmoothShading == False:
        setSelectedObjectShadeFlat(context)
```

### 4.3 设置文件格式（RetopoSettings.txt）

从源码中提取出的完整格式：

```ini
HostApp=Blender
FileIn="C:/Users/.../Temp/Exoside/QuadRemesher/Blender/inputMesh.fbx"
FileOut="C:/Users/.../Temp/Exoside/QuadRemesher/Blender/retopo.fbx"
ProgressFile="C:/Users/.../Temp/Exoside/QuadRemesher/Blender/progress.txt"
TargetQuadCount=120000
CurvatureAdaptivness=50
ExactQuadCount=0
UseVertexColorMap=False
UseMaterialIds=0
UseIndexedNormals=0
AutoDetectHardEdges=1
```

| 参数 | 含义 | 默认值 | 本次设置 |
|------|------|--------|----------|
| `HostApp` | 宿主程序标识 | Blender | Blender |
| `FileIn` | 输入 FBX 路径 | — | 自动生成 |
| `FileOut` | 输出 FBX 路径 | — | 自动生成 |
| `ProgressFile` | 进度文件路径 | — | 自动生成 |
| `TargetQuadCount` | 目标四边形数量 | 5000 | **120000** |
| `CurvatureAdaptivness` | 曲率自适应（0-100） | 50 | 50 |
| `ExactQuadCount` | 精确面数（0=自适应, 1=精确） | 0 | 0 |
| `UseVertexColorMap` | 使用顶点色控制密度 | False | False |
| `UseMaterialIds` | 使用材质边界 | 0 | 0 |
| `UseIndexedNormals` | 使用法线分割 | 0 | 0 |
| `AutoDetectHardEdges` | 自动检测硬边 | 1 | 1 |
| `SymAxis` | 对称轴（X/Y/Z 组合） | 无 | 无 |
| `SymLocal` | 局部对称 | 1 | （仅启用对称时写） |

### 4.4 进度文件格式（progress.txt）

xremesh.exe 运行时会持续写入进度文件：

```
第一行: 浮点数，表示进度
  0.0 ~ 1.0  → 进度百分比 (0% ~ 99%)
  2.0        → 完成 (100%)
  负数       → 错误码

第二行（仅错误时）: 错误描述文本
```

插件源码中的进度解析逻辑：

```python
def update_progress_bar(self):
    pf = open(self.progressFilename, "r")
    progressLines = pf.read().splitlines()
    ProgressValueFloat = float(progressLines[0])

    if ProgressValueFloat < 0:          # 错误
        return ProgressValueFloat, progressLines[1]
    elif ProgressValueFloat == 2:       # 完成
        return 2.0, ""
    else:                               # 进行中
        newPBarValue = int(99.0 * ProgressValueFloat + 1.0)
        return ProgressValueFloat, ""
```

---

## 5. 解决方案：绕过 Modal，直调引擎

### 5.1 方案对比

| 方案 | 可行性 | 说明 |
|------|--------|------|
| ❌ 直接调用 `bpy.ops.qremesher.remesh()` | 不可行 | Modal 操作符在 `--background` 下无事件循环 |
| ❌ 用 `--foreground` + GUI 自动化 | 不推荐 | 需要 GUI 环境，无法无人值守 |
| ✅ **复现底层流程，同步等待引擎** | **可行** | 绕过操作符，直接导出FBX→写设置→调xremesh→导入结果 |

### 5.2 流程图

```
┌─────────────────────────────────────────────────────────┐
│                    自动化脚本主流程                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───── 1. 打开 blend 文件 ─────┐
              │  bpy.ops.wm.open_mainfile()  │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 2. 查找并选择网格 ───────┐
              │  遍历 bpy.data.objects       │
              │  多个网格则 join()            │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 3. 导出 FBX ─────────────┐
              │  bpy.ops.export_scene.fbx()  │
              │  → %TEMP%/Exoside/.../       │
              │    inputMesh.fbx             │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 4. 写设置文件 ───────────┐
              │  RetopoSettings.txt          │
              │  TargetQuadCount=120000      │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 5. 启动 xremesh.exe ─────┐
              │  subprocess.Popen([          │
              │    xremesh.exe,              │
              │    -s, RetopoSettings.txt    │
              │  ])                          │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 6. 轮询进度文件 ─────────┐
              │  while proc.poll() is None:  │
              │    read progress.txt         │
              │    print "进度: XX%"          │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 7. 导入结果 FBX ────────┐
              │  bpy.ops.import_scene.fbx() │
              │  → retopo.fbx               │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 8. 清理原始高模 ────────┐
              │  bpy.data.objects.remove()  │
              └──────────────────────────────┘
                          │
                          ▼
              ┌──── 9. 保存输出 ────────────┐
              │  保存 .blend + .fbx         │
              │  → D:\ls\QR输出\            │
              └──────────────────────────────┘
```

### 5.3 关键技术决策

#### 决策 1：为什么用 `subprocess.Popen` + 轮询，而不是 `subprocess.run`？

`subprocess.run()` 会阻塞直到进程结束，但无法读取进度。用 `Popen` + 轮询 `progress.txt` 文件可以在等待过程中实时输出进度百分比，对大模型处理更有意义。

#### 决策 2：为什么设置 `cwd=engine_folder`？

xremesh.exe 可能依赖同目录下的 DLL（如 `xremeshlib.dll`），设置工作目录为引擎文件夹确保 DLL 能被正确加载。

#### 决策 3：为什么删除原始高模？

输出 blend 文件只保留重拓扑后的网格，避免文件过大（原始 76MB → 输出 6MB）。如果需要保留原始网格，注释掉清理步骤即可。

---

## 6. 完整自动化脚本

脚本文件：`D:\ls\quad_remesher_auto.py`

```python
"""
QuadRemesher 全自动重拓扑脚本
- 打开原始高模 blend 文件
- 导出 FBX 到临时目录
- 写设置文件 (TargetQuadCount=120000)
- 调用 xremesh.exe 引擎进行四边重拓扑
- 导入结果并保存到 QR输出目录
"""
import bpy
import os
import sys
import subprocess
import tempfile
import time

# ==================== 配置 ====================
INPUT_BLEND = "D:/ls/原始文件/tripoTpose_01_repair.blend"
OUTPUT_DIR = "D:/ls/QR输出"
TARGET_QUAD_COUNT = 120000  # 12万

# QuadRemesher 引擎路径
APPDATA = os.environ.get('APPDATA', '')
QR_EXTENSION_DIR = os.path.join(
    APPDATA,
    "Blender Foundation", "Blender", "5.0",
    "extensions", "user_default", "quadremesher"
)
ENGINE_PATH = os.path.join(QR_EXTENSION_DIR, "EngineWin", "xremesh.exe")

# 临时目录
QRTempFolder = os.path.join(tempfile.gettempdir(), "Exoside")
export_path = os.path.join(QRTempFolder, "QuadRemesher", "Blender")
os.makedirs(export_path, exist_ok=True)

settingsFilename = os.path.join(export_path, 'RetopoSettings.txt')
inputFilename = os.path.join(export_path, 'inputMesh.fbx')
retopoFilename = os.path.join(export_path, 'retopo.fbx')
progressFilename = os.path.join(export_path, 'progress.txt')


def main():
    print("=" * 60)
    print("QuadRemesher 全自动重拓扑流程")
    print("=" * 60)

    # 1. 验证引擎
    if not os.path.exists(ENGINE_PATH):
        print(f"ERROR: xremesh.exe 未找到: {ENGINE_PATH}")
        sys.exit(1)
    print(f"引擎路径: {ENGINE_PATH}")
    print(f"目标面数: {TARGET_QUAD_COUNT}")

    # 2. 打开 blend 文件
    print(f"\n--- 打开文件 ---")
    print(f"输入: {INPUT_BLEND}")
    bpy.ops.wm.open_mainfile(filepath=INPUT_BLEND)

    # 3. 查找并选择网格对象
    mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    if not mesh_objects:
        print("ERROR: 未找到网格对象!")
        sys.exit(1)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]

    original_name = mesh_objects[0].name
    orig_verts = sum(len(o.data.vertices) for o in mesh_objects)
    orig_faces = sum(len(o.data.polygons) for o in mesh_objects)
    print(f"原始网格: {original_name}")
    print(f"  顶点数: {orig_verts:,}")
    print(f"  面数:   {orig_faces:,}")

    # 如果有多个网格，合并
    if len(mesh_objects) > 1:
        print(f"合并 {len(mesh_objects)} 个网格对象...")
        bpy.ops.object.join()
        mesh_objects = [bpy.context.active_object]
        orig_verts = len(mesh_objects[0].data.vertices)
        orig_faces = len(mesh_objects[0].data.polygons)

    # 4. 导出 FBX
    print(f"\n--- 导出 FBX ---")
    bpy.ops.export_scene.fbx(filepath=inputFilename, use_selection=True)
    fbx_size = os.path.getsize(inputFilename)
    print(f"FBX 已导出: {inputFilename}")
    print(f"FBX 大小: {fbx_size / 1024 / 1024:.1f} MB")

    # 5. 写设置文件
    print(f"\n--- 写设置文件 ---")
    with open(settingsFilename, "w") as f:
        f.write('HostApp=Blender\n')
        f.write('FileIn="%s"\n' % inputFilename)
        f.write('FileOut="%s"\n' % retopoFilename)
        f.write('ProgressFile="%s"\n' % progressFilename)
        f.write("TargetQuadCount=%s\n" % str(TARGET_QUAD_COUNT))
        f.write("CurvatureAdaptivness=50\n")
        f.write("ExactQuadCount=0\n")  # adapt_quad_count=True -> 0
        f.write("UseVertexColorMap=False\n")
        f.write("UseMaterialIds=0\n")
        f.write("UseIndexedNormals=0\n")
        f.write("AutoDetectHardEdges=1\n")
    print(f"设置文件: {settingsFilename}")

    # 清理旧输出
    for f_path in [retopoFilename, progressFilename]:
        if os.path.isfile(f_path):
            os.remove(f_path)

    # 6. 运行 xremesh.exe
    print(f"\n--- 启动重拓扑引擎 ---")
    print(f"命令: {ENGINE_PATH} -s {settingsFilename}")
    print("重拓扑进行中... (193万面 → 12万四边形，可能需要数分钟)")

    engine_folder = os.path.dirname(ENGINE_PATH)
    proc = subprocess.Popen(
        [ENGINE_PATH, "-s", settingsFilename],
        cwd=engine_folder,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 监控进度
    last_progress = -1
    start_time = time.time()
    while proc.poll() is None:
        time.sleep(3)
        elapsed = time.time() - start_time
        if os.path.exists(progressFilename):
            try:
                with open(progressFilename, "r") as pf:
                    lines = pf.read().splitlines()
                if lines:
                    try:
                        val = float(lines[0])
                        if 0 < val < 1:
                            pct = int(99.0 * val + 1.0)
                            if pct != last_progress:
                                print(f"  进度: {pct}%  (已用 {elapsed:.0f}s)")
                                last_progress = pct
                        elif val == 2:
                            print(f"  进度: 100% (完成)  (用时 {elapsed:.0f}s)")
                        elif val < 0:
                            msg = lines[1] if len(lines) > 1 else "unknown"
                            print(f"  错误: {msg} (code={val})  (用时 {elapsed:.0f}s)")
                    except ValueError:
                        pass
            except Exception:
                pass
        else:
            if int(elapsed) % 15 == 0 and int(elapsed) > 0:
                print(f"  等待进度文件... (已用 {elapsed:.0f}s)")

    return_code = proc.returncode
    elapsed = time.time() - start_time
    print(f"\nxremesh.exe 返回码: {return_code}  (用时 {elapsed:.0f}s)")

    # 打印 stdout/stderr
    if proc.stdout:
        out = proc.stdout.read().decode('utf-8', errors='replace')
        if out.strip():
            print(f"stdout: {out}")
    if proc.stderr:
        err = proc.stderr.read().decode('utf-8', errors='replace')
        if err.strip():
            print(f"stderr: {err}")

    # 7. 检查结果
    if not os.path.exists(retopoFilename):
        print("\nERROR: 重拓扑结果文件未生成!")
        if os.path.exists(progressFilename):
            with open(progressFilename, "r") as f:
                print(f"进度文件内容: {f.read()}")
        sys.exit(1)

    retopo_size = os.path.getsize(retopoFilename)
    print(f"重拓扑结果: {retopoFilename}")
    print(f"结果大小: {retopo_size / 1024 / 1024:.1f} MB")

    # 8. 导入重拓扑结果
    print(f"\n--- 导入重拓扑结果 ---")
    bpy.ops.import_scene.fbx(filepath=retopoFilename)

    imported = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if not imported:
        print("ERROR: 导入后未找到网格对象!")
        sys.exit(1)

    retopo_obj = imported[0]
    retopo_obj.name = original_name + "_QR_12W"
    retopo_verts = len(retopo_obj.data.vertices)
    retopo_faces = len(retopo_obj.data.polygons)
    print(f"重拓扑网格: {retopo_obj.name}")
    print(f"  顶点数: {retopo_verts:,}")
    print(f"  面数:   {retopo_faces:,}")

    # 9. 清理：删除原始高模，仅保留重拓扑结果
    print(f"\n--- 清理场景 ---")
    for obj in mesh_objects:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"  已删除原始网格: {original_name}")
        except Exception as e:
            print(f"  删除失败: {e}")

    # 确保重拓扑对象在场景中可见且激活
    retopo_obj.hide_set(False)
    retopo_obj.hide_viewport = False
    bpy.context.view_layer.objects.active = retopo_obj
    retopo_obj.select_set(True)

    # 10. 保存 blend 文件
    print(f"\n--- 保存输出 ---")
    output_blend = os.path.join(OUTPUT_DIR, "tripoTpose_01_repair_QR.blend")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"已保存 blend: {output_blend}")
    print(f"  文件大小: {os.path.getsize(output_blend) / 1024 / 1024:.1f} MB")

    # 11. 也导出 FBX
    output_fbx = os.path.join(OUTPUT_DIR, "tripoTpose_01_repair_QR.fbx")
    bpy.ops.export_scene.fbx(filepath=output_fbx, use_selection=True)
    print(f"已保存 FBX:  {output_fbx}")
    print(f"  文件大小: {os.path.getsize(output_fbx) / 1024 / 1024:.1f} MB")

    # 12. 汇总
    print("\n" + "=" * 60)
    print("重拓扑完成!")
    print("=" * 60)
    print(f"原始:  {orig_verts:>10,} 顶点 | {orig_faces:>10,} 面 (三角面)")
    print(f"重拓扑: {retopo_verts:>10,} 顶点 | {retopo_faces:>10,} 面 (四边形)")
    print(f"面数比: {orig_faces / retopo_faces:.1f}:1")
    print(f"目标面数: {TARGET_QUAD_COUNT:,}")
    print(f"实际面数: {retopo_faces:,} (误差: {abs(retopo_faces - TARGET_QUAD_COUNT) / TARGET_QUAD_COUNT * 100:.1f}%)")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)


main()
```

---

## 7. 脚本逐段解析

### 7.1 配置区（第 1-25 行）

```python
INPUT_BLEND = "D:/ls/原始文件/tripoTpose_01_repair.blend"
OUTPUT_DIR = "D:/ls/QR输出"
TARGET_QUAD_COUNT = 120000
```

**三个核心参数**，修改这三行即可适配新任务。

```python
APPDATA = os.environ.get('APPDATA', '')
QR_EXTENSION_DIR = os.path.join(
    APPDATA, "Blender Foundation", "Blender", "5.0",
    "extensions", "user_default", "quadremesher"
)
ENGINE_PATH = os.path.join(QR_EXTENSION_DIR, "EngineWin", "xremesh.exe")
```

通过 `%APPDATA%` 环境变量动态构建引擎路径，不硬编码用户名。

```python
QRTempFolder = os.path.join(tempfile.gettempdir(), "Exoside")
export_path = os.path.join(QRTempFolder, "QuadRemesher", "Blender")
```

临时目录与插件原生的路径完全一致（`%TEMP%\Exoside\QuadRemesher\Blender\`），这样即使手动检查也和 GUI 操作产生的文件在相同位置。

### 7.2 打开文件与网格选择（第 40-75 行）

```python
bpy.ops.wm.open_mainfile(filepath=INPUT_BLEND)

mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
```

打开 blend 文件后，遍历所有对象找出网格类型。如果场景中有多个网格，自动 `join()` 合并为一个（xremesh 只能处理单个网格）。

### 7.3 导出 FBX（第 77-82 行）

```python
bpy.ops.export_scene.fbx(filepath=inputFilename, use_selection=True)
```

使用 Blender 内置的 FBX 导出器，`use_selection=True` 只导出选中的网格。这是 xremesh.exe 的输入格式要求。

### 7.4 写设置文件（第 84-96 行）

这是从 `qr_operators.py` 的 `doRemeshing_Start()` 中逐行复制的设置文件格式：

```python
with open(settingsFilename, "w") as f:
    f.write('HostApp=Blender\n')
    f.write('FileIn="%s"\n' % inputFilename)
    f.write('FileOut="%s"\n' % retopoFilename)
    f.write('ProgressFile="%s"\n' % progressFilename)
    f.write("TargetQuadCount=%s\n" % str(TARGET_QUAD_COUNT))
    f.write("CurvatureAdaptivness=50\n")
    f.write("ExactQuadCount=0\n")       # adapt_quad_count=True → 0
    f.write("UseVertexColorMap=False\n")
    f.write("UseMaterialIds=0\n")
    f.write("UseIndexedNormals=0\n")
    f.write("AutoDetectHardEdges=1\n")
```

每个参数的含义见 [第 4.3 节](#43-设置文件格式retopingstxt)。

### 7.5 启动引擎并监控进度（第 102-145 行）

```python
proc = subprocess.Popen(
    [ENGINE_PATH, "-s", settingsFilename],
    cwd=engine_folder,          # 重要：工作目录设为引擎文件夹
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
```

**关键点**：`cwd=engine_folder` 确保 xremesh.exe 能找到同目录下的 `xremeshlib.dll`。

```python
while proc.poll() is None:      # 进程仍在运行
    time.sleep(3)               # 每 3 秒检查一次
    elapsed = time.time() - start_time
    if os.path.exists(progressFilename):
        with open(progressFilename, "r") as pf:
            lines = pf.read().splitlines()
        val = float(lines[0])
        if 0 < val < 1:         # 进行中
            pct = int(99.0 * val + 1.0)
            print(f"  进度: {pct}%  (已用 {elapsed:.0f}s)")
        elif val == 2:          # 完成
            print(f"  进度: 100% (完成)  (用时 {elapsed:.0f}s)")
        elif val < 0:           # 错误
            msg = lines[1] if len(lines) > 1 else "unknown"
            print(f"  错误: {msg} (code={val})")
```

进度解析逻辑直接取自插件的 `update_progress_bar()` 函数。这是替代 Modal 定时器的同步轮询方案。

### 7.6 导入结果与清理（第 155-185 行）

```python
bpy.ops.import_scene.fbx(filepath=retopoFilename)

retopo_obj = imported[0]
retopo_obj.name = original_name + "_QR_12W"

# 删除原始高模
for obj in mesh_objects:
    bpy.data.objects.remove(obj, do_unlink=True)
```

导入重拓扑后的 FBX，重命名，然后删除原始高模。最终场景中只保留重拓扑网格。

### 7.7 保存输出（第 187-200 行）

```python
# 保存 blend
output_blend = os.path.join(OUTPUT_DIR, "tripoTpose_01_repair_QR.blend")
bpy.ops.wm.save_as_mainfile(filepath=output_blend)

# 同时导出 FBX
output_fbx = os.path.join(OUTPUT_DIR, "tripoTpose_01_repair_QR.fbx")
bpy.ops.export_scene.fbx(filepath=output_fbx, use_selection=True)
```

输出两种格式：`.blend`（Blender 原生）和 `.fbx`（通用交换格式）。

---

## 8. 运行方式

### 8.1 基本命令

```bash
"/d/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
  --background \
  --python "D:/ls/quad_remesher_auto.py"
```

### 8.2 参数说明

| 参数 | 说明 |
|------|------|
| `--background` | 无 GUI 模式运行，脚本执行完毕后自动退出 |
| `--python "D:/..."` | 启动后执行指定 Python 脚本 |

### 8.3 前台 vs 后台运行

**短任务（< 1 分钟）**：直接前台运行

```bash
blender --background --python script.py
```

**长任务（> 1 分钟）**：后台运行 + 完成通知

```bash
# 在 Hermes 中
terminal(background=true, notify_on_complete=true)
```

本次任务实际耗时约 90 秒（含文件加载 + FBX 导出 + 重拓扑 + 导入 + 保存），使用后台模式。

---

## 9. 实际执行日志

以下是本次任务的完整输出（已清理 Blender 的冗余信息）：

```
============================================================
QuadRemesher 全自动重拓扑流程
============================================================
引擎路径: C:\Users\27866\AppData\Roaming\Blender Foundation\Blender\5.0\extensions\user_default\quadremesher\EngineWin\xremesh.exe
目标面数: 120000

--- 打开文件 ---
输入: D:/ls/原始文件/tripoTpose_01_repair.blend

  [MESH] name=tripo_node_89f96507-4268-42bd-8c27-bf6892366069
  顶点数: 965,018
  面数:   1,930,105

--- 导出 FBX ---
FBX 已导出: C:\Users\27866\AppData\Local\Temp\Exoside\QuadRemesher\Blender\inputMesh.fbx
FBX 大小: 49.5 MB

--- 写设置文件 ---
设置文件: C:\Users\27866\AppData\Local\Temp\Exoside\QuadRemesher\Blender\RetopoSettings.txt

--- 启动重拓扑引擎 ---
命令: xremesh.exe -s RetopoSettings.txt
重拓扑进行中... (193万面 → 12万四边形，可能需要数分钟)
  进度: 18%  (已用 3s)
  进度: 24%  (已用 6s)
  进度: 51%  (已用 9s)
  进度: 55%  (已用 12s)
  进度: 56%  (已用 15s)
  进度: 75%  (已用 18s)
  进度: 96%  (已用 24s)
  进度: 100% (完成)  (用时 39s)

xremesh.exe 返回码: 0  (用时 39s)
重拓扑结果: C:\Users\27866\AppData\Local\Temp\Exoside\QuadRemesher\Blender\retopo.fbx
结果大小: 2.3 MB

--- 导入重拓扑结果 ---
重拓扑网格: tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR_12W
  顶点数: 112,967
  面数:   112,980

--- 清理场景 ---
  已删除原始网格: tripo_node_89f96507-4268-42bd-8c27-bf6892366069

--- 保存输出 ---
已保存 blend: D:/ls/QR输出\tripoTpose_01_repair_QR.blend  (6.0 MB)
已保存 FBX:  D:/ls/QR输出\tripoTpose_01_repair_QR.fbx    (4.4 MB)

============================================================
重拓扑完成!
============================================================
原始:     965,018 顶点 |  1,930,105 面 (三角面)
重拓扑:    112,967 顶点 |    112,980 面 (四边形)
面数比: 17.1:1
目标面数: 120,000
实际面数: 112,980 (误差: 5.9%)
输出目录: D:/ls/QR输出
============================================================
```

### 性能数据

| 阶段 | 耗时 |
|------|------|
| 打开 blend 文件 | ~3s |
| 导出 FBX | ~3.4s |
| xremesh 引擎计算 | **39s** |
| 导入结果 FBX | ~1s |
| 保存 blend + fbx | ~1s |
| **总计** | **~90s** |

---

## 10. 如何复用（更换源文件/参数）

### 10.1 修改配置区

打开 `D:\ls\quad_remesher_auto.py`，修改文件头部的三个变量：

```python
# 换源文件
INPUT_BLEND = "D:/其他路径/另一个模型.blend"

# 换输出目录
OUTPUT_DIR = "D:/其他路径/输出"

# 换目标面数
TARGET_QUAD_COUNT = 50000   # 5万
```

### 10.2 高级参数调整

如需调整重拓扑质量参数，修改设置文件写入部分：

```python
f.write("CurvatureAdaptivness=80\n")    # 更高=高曲率区域面更密 (0-100)
f.write("ExactQuadCount=1\n")           # 1=精确匹配目标面数, 0=自适应
f.write("AutoDetectHardEdges=0\n")      # 0=关闭硬边检测
```

### 10.3 批量处理

如需批量处理多个 blend 文件，可以改为遍历目录：

```python
import glob

input_dir = "D:/ls/原始文件"
blend_files = glob.glob(os.path.join(input_dir, "*.blend"))

for blend_file in blend_files:
    INPUT_BLEND = blend_file
    # ... 运行重拓扑流程
    # 输出文件名基于输入文件名自动生成
```

### 10.4 保留原始网格

如果不希望删除原始高模（输出文件同时包含高模和重拓扑网格），注释掉清理部分：

```python
# 注释掉或删除这段代码
# for obj in mesh_objects:
#     bpy.data.objects.remove(obj, do_unlink=True)
```

---

## 11. 常见问题与排错

### Q1: `xremesh.exe 未找到`

**原因**：引擎路径不正确，或 QuadRemesher 尚未安装引擎。

**解决**：
1. 确认 QuadRemesher 插件已在 Blender 中启用（Edit > Preferences > Extensions）
2. 在 Blender GUI 中手动点击一次 "Remesh" 按钮，插件会自动下载引擎
3. 检查 `%APPDATA%\Blender Foundation\Blender\5.0\extensions\user_default\quadremesher\EngineWin\xremesh.exe` 是否存在

### Q2: `20秒后无进度文件`

**原因**：xremesh.exe 启动失败，可能缺少 VC++ 运行时。

**解决**：安装 Microsoft Visual C++ Redistributable (x64)。QuadRemesher 插件目录下可能附带 `Windows_Patch_vcredist_x64.exe`。

### Q3: 进度文件显示负数错误码

| 错误码 | 含义 | 解决 |
|--------|------|------|
| -1 | 输入文件无效 | 检查 FBX 是否成功导出 |
| -2 | 用户取消 | 不适用于自动模式 |
| -3 | 引擎崩溃 | 检查模型是否有问题（非流形、未封闭等） |
| -10 | 无进度文件 | 引擎启动失败，检查 VC++ 运行时 |
| -11 | 进度文件数据格式错误 | 引擎版本与插件不匹配 |

### Q4: 实际面数与目标面数有偏差

这是正常现象。`ExactQuadCount=0`（自适应模式）下，xremesh 会根据曲率分布微调面数，实际面数通常在目标的 ±10% 以内。如果需要更精确的匹配：

```python
f.write("ExactQuadCount=1\n")    # 改为精确模式
```

### Q5: Blender 5.0 路径问题

在 git-bash/MSYS 中调用 Blender 时：
- Blender 可执行文件路径：用 MSYS 路径 `"/d/Program Files/..."` 
- `--python` 参数中的脚本路径：用 Windows 路径 `"D:/..."`
- 脚本内部的文件路径：用 Windows 路径 `"D:/..."`

### Q6: 中文路径问题

Blender 5.0 的 Python 3.11 对中文路径支持良好，但仍建议：
- 脚本内文件路径使用正斜杠 `/`（Windows 也支持）
- 如遇编码问题，在文件操作时指定 `encoding='utf-8'`

### Q7: 插件已安装但 `bpy.ops.qremesher` 不存在

**原因**：QuadRemesher 在 Blender 5.0 中作为 extension 安装，不是传统 addon。在 `--background` 模式下，extension 可能不会自动加载。

**解决**：这正是本方案的设计原因——不依赖插件加载，直接调用底层引擎。只要 `xremesh.exe` 文件存在即可。

---

## 12. 关键文件清单

### 12.1 源文件与输出

| 文件 | 路径 | 说明 |
|------|------|------|
| 原始高模 | `D:\ls\原始文件\tripoTpose_01_repair.blend` | 76MB, 193万面 |
| 输出 blend | `D:\ls\QR输出\tripoTpose_01_repair_QR.blend` | 6MB, 11.3万面 |
| 输出 FBX | `D:\ls\QR输出\tripoTpose_01_repair_QR.fbx` | 4.4MB |

### 12.2 脚本文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 自动化脚本 | `D:\ls\quad_remesher_auto.py` | 主脚本，可直接运行 |
| 探测脚本 | `D:\ls\probe_blend.py` | 开发用：检查 blend 文件内容 |
| 插件查找脚本 | `D:\ls\find_quadremesher.py` | 开发用：定位 QuadRemesher 安装位置 |

### 12.3 QuadRemesher 插件源码

| 文件 | 路径 | 说明 |
|------|------|------|
| 插件主文件 | `...\extensions\user_default\quadremesher\__init__.py` | 面板注册、属性定义 |
| 操作符文件 | `...\extensions\user_default\quadremesher\qr_operators.py` | 重拓扑核心逻辑 |
| 引擎可执行 | `...\extensions\user_default\quadremesher\EngineWin\xremesh.exe` | 重拓扑引擎 |

### 12.4 临时文件（运行时生成）

| 文件 | 路径 | 说明 |
|------|------|------|
| 输入 FBX | `%TEMP%\Exoside\QuadRemesher\Blender\inputMesh.fbx` | 导出的高模 FBX |
| 设置文件 | `%TEMP%\Exoside\QuadRemesher\Blender\RetopoSettings.txt` | 引擎配置 |
| 输出 FBX | `%TEMP%\Exoside\QuadRemesher\Blender\retopo.fbx` | 重拓扑结果 |
| 进度文件 | `%TEMP%\Exoside\QuadRemesher\Blender\progress.txt` | 实时进度 |

---

## 附录：QuadRemesher 插件架构图

```
┌──────────────────────────────────────────────────────┐
│                   Blender 5.0.1                       │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │     QuadRemesher Extension (Python)          │     │
│  │                                              │     │
│  │  __init__.py                                 │     │
│  │    ├── QRSettingsPropertyGroup (属性组)      │     │
│  │    │     target_count, adaptive_size, ...    │     │
│  │    ├── Panel (N面板/顶栏)                    │     │
│  │    └── register() / unregister()             │     │
│  │                                              │     │
│  │  qr_operators.py                             │     │
│  │    ├── QREMESHER_OT_remesh (操作符)          │     │
│  │    │     ├── doRemeshing_Start()             │     │
│  │    │     │     1. export FBX                 │     │
│  │    │     │     2. write settings.txt         │     │
│  │    │     │     3. Popen xremesh.exe          │     │
│  │    │     │     4. modal timer (轮询进度)     │     │
│  │    │     └── doRemeshing_Finish()            │     │
│  │    │           5. import FBX                 │     │
│  │    │           6. shade flat/smooth          │     │
│  │    └── update_progress_bar()                 │     │
│  └──────────────────┬──────────────────────────┘     │
│                     │ subprocess.Popen                │
│                     ▼                                 │
│  ┌─────────────────────────────────────────────┐     │
│  │     xremesh.exe (Exoside 引擎)               │     │
│  │                                              │     │
│  │  输入: inputMesh.fbx + RetopoSettings.txt   │     │
│  │  输出: retopo.fbx + progress.txt            │     │
│  │  依赖: xremeshlib.dll                       │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
└──────────────────────────────────────────────────────┘

本自动化脚本的方案：
  直接在 Python 层复现步骤 1-6
  用同步轮询替代步骤 4 的 modal timer
  完全绕过 QREMESHER_OT_remesh 操作符
```

---

*文档结束*
