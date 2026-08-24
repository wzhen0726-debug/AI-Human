# 05骨骼绑定 — 半自动打点方案（参照 01a 模式）

**日期**: 2026-08-24  |  **状态**: ✅ 已交付

## 用户操作（参照 01a 的 place_eyelid_markers.py）

1. **双击打开** `06_rig_markers.blend`（Blender 5.2）
2. 在 3D 视图中 **选中标记点（彩色小球）** → 按 **G** 拖动到正确关节位置
   - 标记点自动吸附在模型表面（Shrinkwrap 约束）
   - 穿模可见（show_in_front）
3. 全部放好后 → **Ctrl+S** 保存

> 对比 01a 的眼裂轮廓标记：同样用 Empty 球体 + Shrinkwrap + show_in_front，用户操作完全一致。

## 13 个标记点

| 分组 | 标记点 | 颜色 | 初始位置（自动预置） |
|------|--------|------|---------------------|
| 中线 | 头顶、颈根、会阴 | 🟡 黄色 | 头顶 Z=1.79 / 颈根 Z=1.48 / 会阴 Z=0.90 |
| 左臂 | 左肩、左肘、左腕 | 🔴 红色 | Z=1.43（手臂水平） |
| 右臂 | 右肩、右肘、右腕 | 🔵 蓝色 | Z=1.43（手臂水平） |
| 左腿 | 左膝、左踝 | 🟢 绿色 | 膝 Z=0.36 / 踝 Z=0.09 |
| 右腿 | 右膝、右踝 | 🟠 橙色 | 膝 Z=0.36 / 踝 Z=0.09 |

标记点命名: `LM_<id>_<中文名>`（如 `LM_Shoulder_L_左肩`），位于集合 `LM_Rig` 中。

## 生成骨骼

标记点调好后，运行读取脚本（参照 01a 的 read_eyelid_markers.py）：

```bash
set B="D:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

%B% --background --factory-startup --python scripts/rig_from_markers.py ^
  -- --markers 06_rig_markers.blend --output 06_rig_final.glb
```

从标记点位置自动构建 22 骨骼 Mixamo 标准骨架 + 自动权重 + 导出 GLB。

## 脚本

| 脚本 | 功能 | 参照 01a |
|------|------|----------|
| `rig_semiauto_setup.py` | 初始化：加载模型+眼球+预置标记点 | `place_eyelid_markers.py` |
| `rig_from_markers.py` | 读取标记点→生成骨骼+权重+GLB | `read_eyelid_markers.py` |
| `check_markers.py` | 检查标记点完整性 | - |
| `analyze_model.py` | 模型几何分析 | - |
| `diagnose_bones.py` | 骨骼位置诊断 | - |

## 输出

| 文件 | 说明 | 大小 |
|------|------|------|
| `06_rig_markers.blend` | 交互式打点文件（打开即用） | 8.5 MB |
| `06_rig_final.blend` | 绑定后文件（骨骼+权重） | 7.7 MB |
| `06_rig_final.glb` | 最终 GLB | 34.9 MB |

## 全自动 vs 半自动对比

| 指标 | 全自动（几何检测） | 半自动（标记点） |
|------|-------------------|-----------------|
| 胯部 | Z=0.725（40%，错：找到臀部） | Z=0.900（50%，✅ 正确） |
| 手臂 | 锯齿形（肘低 9cm） | 水平直线 ✅ |
| 膝盖 | 硬编码 0.22H | 用户标记 ✅ |
| 用户操作 | 0 步（全自动） | 0-13 步（微调标记点） |
| 精度 | 厘米级误差 | 目视毫米级 |

## 技术要点

- **Shrinkwrap 约束**：标记点自动吸附在模型表面，拖动时始终贴合（`NEAREST_SURFACE`，`distance=0.0`）
- **show_in_front**：标记点穿模可见，即使被身体挡住也能看到
- **集合管理**：所有标记点在 `LM_Rig` 集合中，方便批量操作
- **无插件依赖**：纯 blend 文件，不需要安装任何 addon
- **Blender 5.2**：`--factory-startup` 避免 better_fbx/FMT-V3 崩溃