# Blender Background 模式 Sculpt Brush 调研

## 核心结论

`bpy.ops.sculpt.brush_stroke` 在 background 模式**可以调用成功，但对网格无实际效果**。
根因不是"无视口"，而是 **tool 系统缺失** —— 无法从默认 Draw brush 切换到 Smooth 等 sculpt brush。

## 调研过程 (2026-07-23)

### 1. 视口上下文检查

background 模式有 `VIEW_3D` area 和 `WINDOW` region:
```python
bpy.context.area        # None (无激活 area)
bpy.context.screen.areas  # [PROPERTIES, OUTLINER, DOPESHEET_EDITOR, VIEW_3D]
```

但 `bpy.context.area` 为 None，需要 `temp_override` 指定。

### 2. brush_stroke 调用成功

用 `temp_override` + 正确参数名，调用不报错:
```python
area = [a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'][0]
region = [r for r in area.regions if r.type == 'WINDOW'][0]
with bpy.context.temp_override(area=area, region=region, active_object=obj, object=obj):
    bpy.ops.sculpt.brush_stroke(
        pen_flip=False,  # 必须在 stroke 外
        stroke=[{
            'name': 'a', 'location': (0,0,0), 'mouse': (0,0), 'mouse_event': (0,0),
            'pressure': 1.0, 'size': 500, 'x_tilt': 0.0, 'y_tilt': 0.0,
            'time': 0.0, 'is_start': True
        }]
    )  # 不报错，SUCCESS
```

**参数名陷阱**: `pen_flip` 是顶层参数（BOOLEAN），不是 stroke 元素属性。stroke 元素只有:
- name, location, mouse, mouse_event, pressure, size, x_tilt, y_tilt, time, is_start

### 3. 但无实际效果

调用后对比顶点位置: `moved = 0/482` — 没有任何顶点移动。

### 4. 根因: tool 系统缺失

```python
bpy.context.tool_settings.sculpt.brush          # read-only, 总是 "Draw"
bpy.context.tool_settings.sculpt.brush = smooth  # AttributeError: read-only
bpy.context.workspace.tools                      # 只有 [builtin.brush], 无 sculpt.smooth
```

Blender 5.1 的 sculpt brush 通过 **tool system** 绑定:
- 每个 tool (如 `sculpt.smooth`) 有自己的默认 brush
- background 模式只有 `builtin.brush`（通用 Draw brush）
- 没有 `sculpt.smooth` tool → 无法激活 Smooth brush

### 5. 资产库可加载但无法激活

```python
lib = r"...\datafiles\assets\brushes\essentials_brushes-mesh_sculpt.blend"
with bpy.data.libraries.load(lib) as (data_from, data_to):
    data_to.brushes = data_from.brushes  # 93 brushes 加载成功
```

但 `sculpt.brush` 仍是 read-only，无法将 Smooth brush 设为活动 brush。

### 6. 结论

| 路径 | 可行性 | 原因 |
|------|--------|------|
| `bpy.ops.sculpt.brush_stroke` | ❌ 无效果 | tool 系统缺失，只能调用 Draw brush，对网格无影响 |
| 资产库加载 Smooth brush | ❌ 无法激活 | `sculpt.brush` read-only |
| **数学模拟 (Laplacian)** | ✅ 唯一方案 | 不依赖 tool 系统，直接操作顶点 |

## 数学模拟方案 (已验证)

```python
# 半径衰减 Laplacian = smooth brush 的数学等价
w = 1.0 - (d / radius) ** 2  # 中心权重最大
v.co = v.co.lerp(avg_of_neighbors, strength * w)
```

详见 `eye-sculpt-cleanup.md`。