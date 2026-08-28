# 半自动打点模板模式（rig marker template）— 2026-08-25/26 踩坑定稿

## 三集合结构（必须）
- `LM_M` 中线点（头顶/颈根/会阴）——**绝不进镜像集合**，否则镜像脚本会造出同位置 `_L` 重复点
- `LM_R` 右侧点（肩/肘/腕/膝/踝）——用户只操作这侧
- `LM_L` 左侧点——脚本生成

## 左侧镜像：驱动器实时同步，不是静态副本
静态拷贝副本会与右侧脱节（用户："再次出现左右两套点，还不能同步镜像"）。
做法：L 点 `driver_add("location", i)` → `fcurve.driver`（注意：是 `driver_add` 返回 FCurve，驱动器在 `.driver` 上），expression `-val`/`val`/`val`（x 取反，y/z 跟随），变量指向 R 点的 location。L 点 `hide_select=True` 锁定防误碰。

## 吸附规则：表面点吸附，关节点绝不吸附
- 中线表面点（头顶/颈根/会阴）：Shrinkwrap NEAREST_SURFACE 可以
- 关节点（肩/肘/腕/膝/踝）：**禁止 Shrinkwrap**——关节在肢体内部，吸附会把点钉在皮肤表面上（用户把肩点打到了三角肌前束表面），骨旋转轴心偏掉，蒙皮变形异常

## 读标记位置：读 matrix_world，不是 location
中线点有约束时，原始 `o.location` 与显示位置脱节（实测：会阴原始 x=-0.078，约束求值后 x=0.000）。绑定脚本若读 location，Hips 会建偏。
用 `o.matrix_world.translation.copy()`（先 `view_layer.update()`）。

## 打开即用视口（-b 可持久化的部分）
可持久化：`shading='MATERIAL'`、`view_distance=3.0`、`view_location=(0,0,0.9)`、`view_rotation=(0.707,0.707,0,0)`（纯正面）、`view_perspective='ORTHO'`。遍历**所有 workspace 的所有 screen 的所有 VIEW_3D area** 都设（残留工作区会有微侧透视）。
不可持久化：活动工具（tool_set_by_id 在 -b 下崩）；用场景内中文文字牌提示用户按 G。

## 文字牌（FONT）朝向
正视相机在 -Y 看 +Y 时，文字法线须朝 -Y → `rotation_euler=(+90°,0,0)`。+Z 平躺、-90° 镜像。**方向必须渲染图实测验证**，别靠推。

## 用户验收点（本类任务）
点有颜色区分、打开即正面正交全身、文字牌不挡操作区、左右同步、中线点在中线上。
