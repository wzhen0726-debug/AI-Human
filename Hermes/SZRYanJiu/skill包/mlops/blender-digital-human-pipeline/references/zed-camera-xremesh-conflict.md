# ZED Camera Conflicts with xremesh.exe

> Session: 2026-07-30 | Blender 5.1 + Quad Remesher Bridge 1.3.2

## Problem

xremesh.exe (Quad Remesher external engine) fails to start or hangs at ~22% progress when ZED camera processes are running.

## Symptoms

1. xremesh.exe starts but exits immediately (no output, no error)
2. xremesh.exe starts but progress.txt stops at ~0.218 (21.8%) and never advances
3. Multiple xremesh.exe processes accumulate, all stuck at same progress

## Root Cause

ZED camera (Zed.exe) occupies GUI resources that xremesh.exe (a GUI-subsystem PE executable) requires for initialization. xremesh.exe has `Subsystem: 2 (Windows GUI)` in its PE header — it needs a GUI session to start, even in background mode.

## Diagnosis

```bash
# Check if ZED is running
tasklist | grep -i zed

# Check if xremesh is stuck
tasklist | grep -i xremesh
cat "C:/Users/<user>/AppData/Local/Temp/Exoside/QuadRemesher/Blender/progress.txt"
```

## Fix

```bash
# Kill ZED before running QR
taskkill /F /T /IM Zed.exe

# Verify ZED is gone
tasklist | grep -i zed || echo "ZED closed"

# Then run xremesh
```

## Critical: ZED Auto-Restart

ZED.exe **automatically restarts** after being killed (system service). Must kill repeatedly during long QR runs. Monitor with:

```bash
# Kill ZED every 30 seconds during QR
for i in $(seq 1 20); do
    taskkill /F /T /IM Zed.exe 2>/dev/null
    sleep 30
done
```

## Additional Issue: xremesh Direct Call Produces Wrong Face Count

When calling xremesh.exe directly (not via Blender operator), the output may have incorrect face count (e.g., 104万面 instead of target 12.5万). This suggests `TargetQuadCount` parameter is not being read correctly. **Workaround**: Use Blender plugin operator (`bpy.ops.qremesher.remesh()`) when possible, or reuse existing QR results.
