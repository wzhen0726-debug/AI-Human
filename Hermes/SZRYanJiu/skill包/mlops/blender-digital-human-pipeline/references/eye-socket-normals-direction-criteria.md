# 眼窝法线方向判据 + Blender 5.1 normal_flip 陷阱 (2026-08-18 v38)

## 1. 错误判据："朝眼球" dot 判据

v35/v37 用 `f.normal.dot(center - fc) < 0` 判断面是否"朝眼球"。
**这是错误的几何判据**，导致倒角带大量面被误判为"正确"而实际是反向。

**证据**：倒角带面 `normal=(0.17, 0.28, 0.94)` 主要朝侧面(+Z)和头内(+Y)，
但 dot>0 被判为"朝眼球正确"，实际用户看到的是黑色/反向面。

**根因**：眼窝是凹陷结构，从前面看进去，所有可见面（碗内壁+倒角带）的法线
都应朝 **-Y（头前/观察者方向）**，而不是朝眼球中心。
- 碗内壁：法线朝 -Y（朝眼开口，可被眼球看到）
- 倒角带：法线朝 -Y（与皮肤连续过渡）
- "朝眼球"判据在倒角带边缘（|Z|大）会误判朝侧面的面为正确

## 2. 正确判据：-Y 统一判据

```python
# 眼窝区所有面（碗+倒角带）法线必须朝头前(-Y)
if f.normal.y > 0:  # 朝头内 = 反向
    f.normal_flip()
```

适用范围：眼窝区（y>center.y, y<center.y+0.02, xz<0.021）。
皮肤面（y<center.y）保持原样不翻。

## 3. Blender 5.1 normal_flip 持久化陷阱

**现象**：`f.normal_flip()` 翻转后打印显示已翻，但保存/重新加载后翻转丢失。

**根因**：`normal_flip()` 只改 bmesh 缓存，`bmesh.update_edit_mesh()` 时 Blender
重新计算法线，翻转被撤销。

**正确做法**：用 `bmesh.ops.reverse_faces(bm, faces=[...])` 标准算子，
同时改绕序+缓存，`update_edit_mesh` 不丢失。

**验证方法**：翻转后立即在 bmesh 里检查 `still_wrong` 数量，
然后保存 blend 重新加载再检查一次，确认翻转持久化。

## 4. 与 recalc_face_normals 的关系

- `recalc_face_normals` 强制集合内所有面统一朝向（ topological 传播）
- 眼窝碗面应朝 -Y，皮肤面应朝外（也是 -Y），二者同向 → recalc 适用
- 但 recalc 可能误翻皮肤面（front_inward 增加），需要几何兜底补漏
- **推荐**：recalc + 几何兜底（-Y 判据），不用"朝眼球"判据

## 5. 诊断脚本陷阱

diagnose_geometry2.py 的坐标计算 bug：`(fc-center).xz.length` 在 Blender 5.1
中可能返回 mm 单位（1000x），导致分桶范围完全错误。
验证诊断脚本时先用已知正确数据 sanity check。
