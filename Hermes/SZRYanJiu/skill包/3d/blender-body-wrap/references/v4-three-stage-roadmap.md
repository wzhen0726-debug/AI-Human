# 三阶段演进路线 (2026-07-29, 基于用户调研材料审核修正)

> Wrap 放弃后的前进路线。完整版见 `方案md记录/v4_前瞻性技术方案/三阶段演进路线.md`。

## 阶段一：MVP 暴力直通（VERIFIED WORKING 2026-07-29）

### 最终验证参数

```python
# QR: 目标125K quad (117,539面, 235K tris, 100% quad, 0 non-manifold)
# 调用 xremesh.exe 直接 (不通过 bpy.ops.qremesher.remesh, 后者在background下cancel)
# RetopoSettings.txt: TargetQuadCount=125000, CurvatureAdaptivness=50

# UV: Smart UV 66°, margin=0.002 (用户纠正: 0.03太保守浪费空间)
bpy.ops.uv.smart_project(
    angle_limit=math.radians(66.0),
    island_margin=0.002,  # 用户优化: 0.03→0.002
    area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
# UV范围: [0.002, 0.998], 0越界点

# Bake: 4K, cage=3mm, ray=5mm (用户纠正: 50mm/100mm太大导致穿透)
bpy.context.scene.render.bake.use_selected_to_active = True  # 必须显式设置
bpy.context.scene.render.bake.cage_extrusion = 0.003   # 3mm
bpy.context.scene.render.bake.max_ray_distance = 0.005  # 5mm
bpy.context.scene.render.bake.margin = 16
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.device = 'CPU'  # GPU可能静默失败
# 结果: mean=0.413, 无全黑

# AI纹理修复: 先修复高模贴图中的肤色渗透, 再烘焙
# 229,644 bleed pixels → 2,674 (98.8% reduction)
```

### MVP 已知问题 (用户已接受继续)

1. **QR重叠** (~29/1000): 衣服+身体双层几何在接缝处产生面重叠。15种程序化修复全部失败（smooth/voxel/push/delete/instant_meshes）。用户GUI手动平滑笔刷可修复。详见 `references/qr-overlap-test-results.md`。
2. **UV碎片化** (~2000岛): Smart UV固有行为，靠bake margin=16px覆盖。
3. **QR无环形线**: 动画时关节拉扯，QR固有局限。

### 审核修正（原材料的错误）

- ❌ "Smart UV 毫无拉伸" — 曲面区域（面部/关节）仍有拉伸，实测仅 2/10
- ⚠️ "浪费 30% 像素" — 方向对但数字未验证
- ✅ "QR 无环形线 → 动画拉扯" — 正确，QR 固有局限

## 阶段二：3D 语义分割 + ARAP Wrap（1-3 个月）

用 AI 分割识别皮肤/衣服区域，分级 wrap：
- 皮肤区域: Shrinkwrap 严格吸附
- 衣服区域: ARAP 只做姿态对齐
- 收益: 继承 MetaHuman 32K 标准 UV

风险: 3D 分割在宽松衣物边界精度差；ARAP 32K 顶点求解速度。

## 阶段三：SMPL-X 参数化逆向拟合（终极，3-6 个月）

Tripo 高模仅作"3D 扫描参考物"，SMPL-X 逆向拟合。

## 三阶段对比

| 维度 | 阶段一(MVP) | 阶段二(分割+ARAP) | 阶段三(SMPL-X) |
|------|-------------|-------------------|----------------|
| 拓扑 | Quad Remesher | MetaHuman Wrap | SMPL-X |
| UV 利用率 | ~80% (margin=0.002) | >90% | >95% |
| 可编辑性 | ❌ | ✅ | ✅ |
| 动画质量 | 关节拉扯 | 良好 | 影视级 |
| 周期 | 1 周 | 1-3 月 | 3-6 月 |
