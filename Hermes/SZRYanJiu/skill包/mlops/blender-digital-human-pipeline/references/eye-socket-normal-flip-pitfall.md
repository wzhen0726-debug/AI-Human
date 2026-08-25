# 眼窝法线：normal_flip/reverse_faces 在 edit mode 中会被回翻 (v36, 2026-08-17)

## 核心发现（重要，之前 v31/v32 未发现）

在 Blender 5.1 **edit mode** 下，`bmesh` 面对象上调用 `normal_flip()` 或
`bmesh.ops.reverse_faces()` 翻转绕序后，紧接着 `bmesh.update_edit_mesh(mesh)`
会把绕序**回翻到创建时的方向**，翻转完全丢失。

实测（在 make_eye_cup 内加 debug 打印）：
```
v36立即翻正: 0/2610已朝眼球, flipped=2610    ← 2610 个新面全部 dot<0，全部被翻转
DEBUG update_edit_mesh后: 0/2610朝眼球       ← update_edit_mesh 后全部回翻成 dot<0
```

`reverse_faces` 同样失败：
```
v36 reverse_faces: 2610/2610已朝眼球, reversed=0   ← 判据认为都不需要翻（因为normal缓存已被污染）
DEBUG update_edit_mesh后: 0/2581朝眼球            ← 保存后依然全错
```

### 为什么之前 v31/v32 用 normal_flip 看起来"有效"

v31/v32 的"几何朝向兜底"用的是 `f.normal_flip()`，且当时验证声称 PASS。但那次
PASS 是假象：验证脚本只检查了 `xz < 0.014` 的碗面内部区域（占碗面 ~75%），漏掉了
倒角带外圈（xz 14-17.5mm）。加上 `update_edit_mesh` 回翻的问题，实际保存到文件后
所有翻转都丢失了。用户 GUI 复查时看到"面朝向更多了/没变"，就是这个原因。

## 唯一可靠的法线方法：bmesh.ops.recalc_face_normals

`recalc_face_normals` 是 Blender 底层 C++ 拓扑传播算子，它修改的是绕序本身，
`update_edit_mesh` **不会覆盖**它的结果。

正确用法（在 edit mode 里，创建完所有新面之后、update_edit_mesh 之前）：
```python
# bowl_zone 必须覆盖全部新面（碗 + 倒角带），xz 半径要用眼窝实际半径 ~17.5mm = 0.0175
bowl_zone = [f for f in bm.faces
             if (f.calc_center_median() - center).xz.length < 0.019
             and f.calc_center_median().y < 0]
# ref_faces = ring0 顶点的相邻皮肤三角面（法线绝对正确，作拓扑传播锚点）
ref_faces = []
for v in ring0_rebuilt:   # ring0 用坐标快照重建，见主 reference 陷阱B
    for f in v.link_faces:
        if len(f.verts) == 3 and f not in ref_faces:
            ref_faces.append(f)
ref_unique = [f for f in ref_faces if f not in bowl_zone]
bmesh.ops.recalc_face_normals(bm, faces=bowl_zone + ref_unique)
```

关键点：
- `bowl_zone` 的 xz 半径必须 ≥ 眼窝轮廓半径（杏仁形宽 ~35mm → 半宽 ~17.5mm）。
  之前 v35 用 `xz < 0.014` 漏掉倒角带外圈，导致 12-16mm 只有 54%、16-20mm 只有 42% 朝眼球。
- 皮肤锚点（ref_faces）必须与碗拓扑连通，recalc 才能传播正确方向。
- 去重用 `f.index` 做 key，不用 `id(f)`（陷阱E）。

## 面朝向判据：不要用 "朝眼中心"

`f.normal.dot(center - fc) > 0` 对碗内壁正确，但对**倒角带外圈错误**——倒角带是
皮肤到碗的过渡面，法线应朝脸前(-Y)，而 center-fc 在倒角带外圈有大的 xz 分量，
dot 会很小甚至为负，导致误判/误翻。

正确判据：眼窝在脸正面，所有结构（皮肤 + 倒角带 + 碗内壁）法线都应朝脸前，
即 `f.normal.y < 0`。

验证时按 xz 距离分桶（0-8 / 8-12 / 12-16 / 16-20mm）检查各桶朝眼球比例应均匀 >95%，
而不是只看整体平均。

## 倒角：圆弧 fillet 替代 线性插值 + Laplace

v32 用"线性插值 + 6 轮 Laplace 圆角化"做倒角，实测被 Laplace 吃掉：
配置 3mm 宽度 → 实际仅 1.1mm（用户反馈"接缝没变化"）。

v36 改用几何上精确的 1/4 圆弧，不需要 Laplace：
```python
F = CHAMFER_FILLET_RINGS  # 4 中间环
W = CHAMFER_WIDTH         # 3mm（内眼角 ring0 径向距离 ~4mm，超过会穿透→非流形边）
D = CHAMFER_DEPTH         # 2mm
for k in range(1, F+2):
    theta = (k/(F+1)) * (math.pi/2)   # 0..π/2
    radial = W * (1 - math.cos(theta)) # 径向内收 0→W
    depth  = D * math.sin(theta)       # 下沉 0→D
    # ring0 处(θ=0)坡度=0 与皮肤切向连续，ring1 处(θ=π/2)垂直下沉
```

## UV 分配

- 碗面：全部用 `avg_uv`（ring0 平均 UV，均匀皮肤色）。
  废弃"径向继承 ring0[i] UV"——它让所有环共用同列 UV，碗面 UV 挤在
  0.008×0.012 极小区域 = 放射状条纹 = UV 错乱。
- 倒角带：ring0 loop 继承皮肤 UV（紧贴皮肤自然过渡），内部环用 ring0 UV。
- `ring0_uv` 必须在创建任何新面之前捕获（陷阱C）。
