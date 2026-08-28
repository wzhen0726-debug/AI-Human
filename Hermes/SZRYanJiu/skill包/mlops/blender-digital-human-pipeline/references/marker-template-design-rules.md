# 半自动打点模板设计规则 (2026-08-26, 全部经用户验收迭代)

## 吸附: 表面点才加Shrinkwrap, 关节点禁止加
- 中线表面标志(头顶/颈根/会阴): Shrinkwrap NEAREST_SURFACE ✅
- 关节中心(肩/肘/腕/膝/踝): **禁止吸附** — 关节在肢体内部, 吸附会把点钉在皮肤表面(用户肩点被打到三角肌前束表面→骨旋转轴心偏前偏外→蒙皮变形异常)。去掉约束时用 evaluated matrix_world 烘bake当前位置, 防止去掉后弹回原始坐标。

## 中线点精确居中: 约束栈顺序
Shrinkwrap NEAREST_SURFACE 会沿不对称网格法线投影偏出中线(实测会阴x=+0.021, 颈根x=-0.037)。修复: 约束栈里Shrinkwrap**之后**追加 LIMIT_LOCATION(min_x=max_x=0, use_transform_limit) — Blender按栈顺序求值, 先吸附表面再钳X=0。

## 左右镜像: 用驱动器实时同步, 禁止静态副本
静态副本生成后与R侧脱节("两套点"+"不能同步镜像"用户两次投诉)。正确做法: L点location三轴加驱动器(x: `-val`, y/z: `val`, SINGLE_PROP指向R点), 且L点 `hide_select=True` 锁选。注意API: `fc=obj.driver_add("location",i); drv=fc.driver`(driver_add返回FCurve不是Driver)。

## 读用户打的点: 必须用 matrix_world.translation
`o.location` 是原始坐标, 与约束求值后的显示位置脱节(实测会阴原始-0.078但显示0.000)→Hips建偏。绑定脚本必须读 `o.matrix_world.translation.copy()`。

## 文字提示牌
- 朝向: 模型正面朝-Y, 相机在-Y侧 → 文字法线须朝-Y, `rotation_euler=(+90°,0,0)`; -90°会看到镜像背面(渲染实测验证)
- 摆放: 别放x≈+0.7,z≈1.44(右手腕区), 放左侧x=-1.1

## -b后台视口持久化(实测结论, 修正旧记忆)
可持久化(经workspace数据块直接写region_3d): shading='MATERIAL', view_distance=3.0, view_location=(0,-3,0.9), view_rotation=四元数, persp='ORTHO'。**不能**持久化: 激活工具(`tool_set_by_id`在-b下ACCESS_VIOLATION硬崩溃, try/except接不住) → 改用场景内FONT文字牌给操作提示。

## 未解决: 标记点颜色
Empty的e.color设置了但视口显示全黑 — 疑似需 `space.shading.color_type='OBJECT'` 才显示物体色, 待下次验证。