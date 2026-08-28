# 打点模板第二轮修正 (2026-08-25 晚) — 中线漂移 + 文字牌镜像

续 `marker-template-2026-08-25-corrections.md`（第一轮：补Shrinkwrap）。本文件记录同日
第二轮用户报错"视口是正面，提示词却朝着顶面；头顶在中间，颈根 会阴却不在中线"的根因与修复。
与第一轮文件冲突时以本文件为准。

## 错误1根因：NEAREST_SURFACE 把中线点带偏（实测数据）

第一轮给全部8点加了 `SHRINKWRAP NEAREST_SURFACE` 后，约束生效位置实测：
- 头顶 x=+0.000（恰好对称，没事）
- 颈根 x=**-0.037**（偏左3.7cm）
- 会阴 x=**+0.021**（偏右2.1cm）

根因：`NEAREST_SURFACE` 沿模型**真实（不对称）表面**投影。人体扫描/生成模型
并非完美镜像，中线附近的最近表面点不在 x=0 上。

**修复**：中线点的约束栈 = SHRINKWRAP + **栈顶追加** LIMIT_LOCATION 钳制 X=0：
```python
c = e.constraints.new('LIMIT_LOCATION')
c.name = "X锁定_保证在中线"
c.use_min_x = c.use_max_x = True
c.min_x = c.max_x = 0.0
c.owner_space = 'WORLD'
```
约束按栈顺序求值：先吸附表面→再钳制X。点既贴皮肤又严格在中线，用户上下拖动也不偏。
侧点（肩肘腕膝踝）不锁，本来就该在 +x。
（中途试过的错误方案：PROJECT投影轴向选择困难、父级空对象+LIMIT_DISTANCE——
约束求值顺序不可靠，均放弃。）

**验证手法**（必须）：读约束**生效后**位置，原始 location 看不出偏移：
```python
dg = bpy.context.evaluated_depsgraph_get()
loc = o.evaluated_get(dg).matrix_world.translation
```
修前修后各测一次，打印对比表给用户。

## 错误2根因：文字牌平躺 + 朝向符号两次才搞对

1. 文字牌默认 `rotation_euler=(0,0,0)` = 平躺面朝上，正视看是一条线 → 用户报"提示词朝着顶面"。
2. 第一次修成 **-90°** → 渲染实测发现是**镜像文字**（看到的是背面）。
3. 正视相机在 −Y 看向 +Y（模型脸朝 −Y）时，文字法线须朝 −Y → **`rotation_euler=(+pi/2, 0, 0)`**。

**教训**：朝向符号依赖相机在哪一侧，推理容易错方向（本次连错两次：先忘旋转，再转反）。
**规则：文字牌朝向不要推理，直接渲染一张正面图做视觉检查。**

## 验证渲染的两个陷阱

1. **深色文字在暗背景不可见**：默认FONT对象无材质=黑色，EEVEE暗场景渲染出来看不清。
   验证渲染时给文字牌挂亮色材质（如绿色 `diffuse_color=(0.1,0.9,0.3,1)`）。
2. **Empty标记点不参与渲染**：验证标记点位置要创建临时小球体
   （半径~0.035，按集合着色：中线黄/右红/左蓝），放在 `evaluated_get(dg)` 位置。
3. Workbench 引擎是后台验证渲染的稳妥选择；不要给 `scn.display.shading.studio_light`
   赋 None（报 enum TypeError）；`bpy.ops.object.mode_set.poll(ctx)` 不是合法调用，别写。

## 视口参数持久化补充（对第一轮清单的确认）

`setup_template_viewport.py` 设置的五项（shading=MATERIAL / dist=3.0 / loc=(0,0,0.9) /
rot=正视四元数(0.707,0.707,0,0) / persp=ORTHO）在 -b 下 `save_as_mainfile()` 后
重开读回全部持久化，对 `bpy.data.workspaces` 里**每个**工作区的每个VIEW_3D area都设。
