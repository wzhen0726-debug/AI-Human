# 眼窝面朝向 v37: 纯几何定向替代recalc (2026-08-17)

v31-v35用"recalc_face_normals + 几何兜底"修碗面朝向，反复出问题。v36删recalc换reverse_faces更糟(0%正确)。
v37彻底研究后找到根本缺陷，改用纯几何定向。实测碗面+倒角带 100% 朝眼球，开放边0。

## 1. recalc_face_normals 的根本缺陷

`bmesh.ops.recalc_face_normals` 强制集合内所有面**统一朝向**。但眼窝场景里两类面的正确朝向**相反**：
- 碗面/倒角带面：朝内 → 指向眼球中心（normal 指向 -Y 方向）
- 皮肤面：朝外 → 指向 -Y（脸前方）

recalc 无法区分，必然翻错一方：
- 种子选到碗面(错误朝向) → 传播到皮肤面 → 皮肤面翻反（front_inward +1039 实测）
- 种子选到皮肤面(正确) → 传播到碗面 → 碗面翻反（背离眼球）

**结论：对"混合朝向"的面集合（碗+皮肤）永远不要用 recalc_face_normals。**
它是为"统一朝向"场景（如全封闭外壳）设计的，对"内外反向"场景（容器内壁 vs 外壳）根本错误。

## 2. v37 正解：纯几何定向（确定性，不碰皮肤面）

只对碗面/倒角带面逐面按几何判据翻正，皮肤面完全不动：

```python
# 关键：先退出EDIT再进，从clean mesh重建bmesh
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.mode_set(mode='EDIT')
bm_new = bmesh.from_edit_mesh(mesh)
bm_new.faces.ensure_lookup_table()

# 碗面+倒角带面确定性朝眼球
for f in bm_new.faces:
    fc = f.calc_center_median()
    if center.y < fc.y < center.y + 0.02 and (fc - center).xz.length < 0.019:
        if f.normal.dot(center - fc) < 0:   # 背离眼球 → 翻
            f.normal_flip()
bmesh.update_edit_mesh(mesh)
```

判据：`center.y < fc.y < center.y + 0.02`（碗深15mm+5mm冗余，排除前方皮肤面 y<center.y 和后脑勺 y>center.y+0.02）+ `xz < 0.019`（覆盖碗半径~14mm + 倒角3mm + ring0~17.5mm）。

几何判据不依赖拓扑传播，对非流形边免疫。

## 3. normal_flip 持久性（v36踩坑的澄清）

v36 的困惑：`normal_flip` 翻转后，`update_edit_mesh` 一调用就全丢（0% 正确）。

**根因**：在"创建面的那个 bmesh"里翻转，`update_edit_mesh` 写入 mesh 时 Blender 基于 mesh 现有状态重算法线，把 bmesh 的翻转覆盖掉。

**解法**：在 **FRESH bmesh**（从 mesh 重建，不是创建时的那个 bmesh）里翻转：
1. `mode_set(OBJECT)` → `mode_set(EDIT)` → `from_edit_mesh(mesh)` 得到干净 bmesh（绕序=mesh 持久状态）
2. 在干净 bmesh 里 `normal_flip()`
3. `update_edit_mesh(mesh)` 写回 → 翻转持久化

实测：fresh bmesh 中 normal_flip 后保存，碗面+倒角带 100% 朝眼球。

## 4. 圆弧 fillet 替代线性+Laplace

v32 线性插值+Laplace 圆角化把 3mm 倒角吃成实测 1.1mm（用户："接缝没变化"）。
Laplace 6轮平滑对窄倒角带是破坏性的——宽度被邻环平均吃掉。

v37 用 1/4 圆弧参数化，宽度精确等于设定值：
```python
F = CHAMFER_FILLET_RINGS  # 中间环数
W = CHAMFER_WIDTH         # 3mm
D = CHAMFER_DEPTH         # 2mm
for k in range(1, F + 2):
    theta = (k / (F + 1)) * (math.pi / 2.0)   # 0..π/2
    radial = W * (1.0 - math.cos(theta))       # 径向内收 0→W
    depth  = D * math.sin(theta)               # 下沉 0→D
    # pos = ring0[i].co + rad_dir * radial + Vector((0, depth, 0))
```
ring0 处(θ=0)坡度=0 与皮肤切向连续，ring1 处(θ=π/2)垂直下沉。实测宽度 min=max=avg=3.00mm。

**宽度上限 3mm**：5mm 在内眼角 R 侧穿透（min 距离 3.22mm → 非流形边 8 个）。

## 5. UV：碗面均匀色 + 倒角带继承

v35 径向继承 ring0 UV → 所有碗面环共用同列 UV → UV 挤在 0.008×0.012 极小区域（放射条纹）。
v37 修复：
- 碗面全部用 `avg_uv`（ring0 皮肤 UV 的平均值，均匀色，无条纹）
- 倒角带 ring0 loop 继承皮肤 UV（自然过渡）
- pole 也用 avg_uv

## 6. front_inward 皮肤面翻反（ring0 松弛副作用）

ring0 松弛（3 次 Laplace 平滑口沿锯齿）+ sliver 溶解会扭曲相邻皮肤三角面，部分法线翻反。
输入模型眼区附近（xz<25mm）仅 35 个朝内面（基线），管线后可能增至 600+。

v37 加"皮肤面恢复"步骤，把被 ring0 松弛误翻的皮肤面翻回：
```python
for f in bm_new.faces:
    fc = f.calc_center_median()
    if fc.y < center.y and (fc - center).xz.length < 0.025:
        if f.normal.y > 0.1:   # 眼区皮肤面应朝外(normal.y<0)
            f.normal_flip()
```
恢复大部分（~464 个），剩 ~146 个在眼区深处（y>center.y，碗面/倒角带区域，不影响碗面朝向）。

## 7. 定量验证纪律（本次踩坑总结）

- **vision 对灰模会误判"破面/黑色面片"**：实测开放边=0、碗面法线100%正确，但 vision 报"大量断裂+法线反向"。
  判断几何正确性必须用定量数据（open_edges 计数、法线 dot 分桶），vision 只做有无/穿帮定性确认。
- 验证脚本的"碗面朝向比例"要**分离碗面/倒角带面/皮肤面**，不能混在一起算——
  皮肤面正确朝向是"背离眼球"，混入会把正确结果误读成"只有80%朝眼球"。
- 端到端验证脚本 hermes_verify_v32.py 的检查项：轮廓尺寸 / custom_normal已删 / open_edges=0 /
  nonmanifold≤1 / ngon=0 / degenerate=0 / UV-zero=0 / 碗面+倒角带朝眼球>98% / 前脸+后脑勺朝内面 vs 基线。
