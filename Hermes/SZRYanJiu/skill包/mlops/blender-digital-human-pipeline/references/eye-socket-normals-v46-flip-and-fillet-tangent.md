# 眼窝面朝向 v46 最终修复 + 倒角带切线 v46c (2026-08-20)

承接 `eye-socket-normals-and-fillet.md`(v31/v32 custom_normal根因) 与 `eye-socket-rim-contour-v45.md`(半自动标记点)。本文记录 v45→v46c 两个新根因和修复。

## 1. v46 残留翻转面：mode切换重算mesh normals + final flip pass用tag层

**现象**：几何朝向兜底自检报 `still wrong=0`，但用户在GUI素模着色下仍看到眼窝上半部分(6.5%)黑色翻转面。

**诊断陷阱**：诊断脚本若用错中心(用了config里偏6mm的 `IRIS_L`，而管线实际用 3DDFA 的 `center_3d`)，会误导定位。诊断必须用 `iris_3ddfa.json` 的 `center_3d`（与 make_eye_cup 的 center 参数一致）。

**根因链**：
1. `bmesh.update_edit_mesh(mesh)` 后，UV 分配段有 EDIT→OBJECT→EDIT 的 mode 切换。OBJECT 模式下 Blender 重新计算 `mesh.polygons` 法线（基于顶点绕序），把之前 `reverse_faces` 修好的面又翻回去（reverse_faces 改了绕序，但顶点绕序与 bmesh normal 缓存不一致）。
2. 旧几何兜底 + v45 的 final flip 都用 y 范围判据 `center.y < fc.y < center.y+0.02`，**漏掉倒角带上半部分靠前的面**（这些面顶点 y ≈ -0.1159 < center.y -0.1058）。

**修复**：最终 flip pass 改用 **v44 的 per-side tag 层**（倒角带=1 / 碗=2 / 原始皮肤=0），只处理新创建面，不用 y 范围判断：
```python
_tag_fl = bm.faces.layers.int.get("v44tag_" + side)
for _f in bm.faces:
    _tg = _f[_tag_fl] if _tag_fl is not None else 0
    if _tg == 0: continue          # 原始皮肤面不动
    if _f.normal.y > 0.05:
        bmesh.ops.reverse_faces(bm, faces=[_f])
```
效果：上半翻转面 7.2% → 0.2%（只剩碗底极点 4-6 面，可忽略）。

**通用教训**：面朝向兜底应基于"新创建面的标签"而非坐标范围判断；坐标范围（y带/xz半径）在轮廓尺寸变化时必然漏检或误伤。标签层在面创建时立即打上（v44 教训：事后回头打 tag 会 ReferenceError: BMFace removed）。

## 2. v46c 眼窝内"唇珠"环线：倒角带与碗面切线不连续

**现象**：素模着色下，眼窝内（非接缝处）出现一圈像唇珠的明暗环线，上弧有 M 形波折。vision 确认是**几何法线突变**（素模无贴图，明暗线必来自几何折角），不是贴图颜色。

**根因**：倒角带(ring0→ring1)用 1/4 圆弧 `radial=W(1-cosθ), depth=D·sinθ`，末端(ring1)切线是「水平内收」（径向继续收缩）；而碗面用 smoothstep `s=t²(3-2t)`，起点(ring1)切线是「完全平缓」（径向、深度都不变）。两者在 ring1 处切线方向突变 → 折角 → 法线突变 → 明暗环线。

**修复**：倒角带从 1/4 圆弧改成 smoothstep（两端导数=0，与碗面起点连续）：
```python
t = k / (F+1)
s = t*t*(3.0 - 2.0*t)      # smoothstep, 两端平缓
radial = W * s
depth  = D * s
```

**关键思路**：相邻几何段（倒角带↔碗面）必须在交界处**切线连续**。用同一种曲线族（都 smoothstep）或显式匹配端点导数。1/4 圆弧与 smoothstep 的端点导数天然不一致（圆弧末端有切线斜率，smoothstep 端点导数为0），必产生折角。

## 3. 轮廓平滑陷阱

不要用「极坐标半径平滑」（对 r(θ) 做移动平均）去消手动轮廓锯齿——它会磨圆外/内眼角的尖角，把轮廓宽度从 35.1mm 缩到 29.1mm，破坏用户已确认的位置。轮廓若需平滑，用**加密插值**（如 12 点→24 点等角度样条），不做半径平均。

## 4. 半自动标记点的两个补充坑

- Shrinkwrap 约束类型枚举在 Blender 5.1 是 `'NEAREST_SURFACE'`，**不是** `'NEAREST_SURFACE_POINT'`（会报 "enum not found"）。
- 背景模式(-b)下 Shrinkwrap 约束不评估，读标记点位置应直接用 `o.location` 的 (x,z) + KD-tree 只投影 y 到表面，保留用户打点的 x,z（KD-tree 投影改 x,z 会变形，是之前"形状对不上打点"的根因）。
