# Quad Remesher (xremesh.exe) 工作流

## 概述
xremesh.exe 可以在 Blender `--background` 模式下通过 `subprocess.Popen` 直接调用，
**不需要** conhost 或 GUI 环境。关键前提：输入网格必须是封闭流形（焊接顶点 + 填补孔洞）。

> **2026-07-31 更新**: 之前认为 xremesh 是 Qt GUI 程序需要交互式窗口环境的结论**已被推翻**。
> 同一会话同一环境下，干净网格 3 次全部成功，破碎网格每次卡 21%。根因是输入网格破碎，
> 不是 Qt/会话问题。

## 调用方式

### 1. 使用 conhost 包装（推荐）
```bash
conhost "C:\Users\Liyunzhong\AppData\Roaming\Blender Foundation\Blender\5.1\extensions\user_default\quadremesher\EngineWin\xremesh.exe" -s "C:\Users\Liyunzhong\AppData\Local\Temp\Exoside\QuadRemesher\Blender\RetopoSettings.txt"
```

conhost 为 xremesh 提供一个控制台窗口环境，使其能够正常运行。

### 2. RetopoSettings.txt 格式
```
HostApp=Blender
FileIn="C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender/inputMesh.fbx"
FileOut="C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender/retopo.fbx"
ProgressFile="C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender/progress.txt"
TargetQuadCount=125000
CurvatureAdaptivness=50
ExactQuadCount=0
UseVertexColorMap=0
UseMaterialIds=0
UseIndexedNormals=0
AutoDetectHardEdges=1
```

**关键参数**：
- `ExactQuadCount=0`：不强制精确匹配目标面数（推荐）
- `ExactQuadCount=1`：强制精确匹配（可能导致 xremesh 崩溃或无法启动）

## 进度监控

xremesh 会实时更新 `progress.txt` 文件，内容为 0.0~1.0 的浮点数。

监控脚本示例：
```bash
while [ ! -f "C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender/retopo.fbx" ]; do
    progress=$(cat "C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender/progress.txt" 2>/dev/null || echo "无进度")
    echo "$(date): 进度 $progress, 等待中..."
    sleep 10
done
echo "QR 完成！"
```

## 已知冲突

### ZED 相机
ZED 相机（Zed.exe）会占用 GUI 资源，导致 xremesh.exe 无法启动或卡死在 21.8%。

**解决方法**：在运行 xremesh 之前杀掉 ZED 进程：
```bash
taskkill /F /T /IM Zed.exe
```

**验证**：
```bash
tasklist | grep -i zed || echo "ZED 已关闭"
tasklist | grep -i xremesh || echo "xremesh 未运行"
```

## 故障排除

### 卡在 21.8%
**原因**：ZED 相机占用 GUI 资源，或 xremesh 在无窗口环境下运行。

**解决**：
1. 杀掉所有 xremesh 和 ZED 进程
2. 使用 `conhost` 包装重新调用

### 生成面数远超目标
**原因**：`ExactQuadCount=1` 可能导致异常行为。

**解决**：改用 `ExactQuadCount=0`，让 xremesh 自适应调整面数。

### Blender operator 在后台模式下失败
**原因**：`bpy.ops.qremesher.remesh()` 使用 modal 模式，需要 window_manager，在 `--background` 模式下无法运行。

**解决**：直接调用 xremesh.exe，不通过 Blender operator。
