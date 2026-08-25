# QR重拓扑后眼窝rim边缘不锐利：方法与定案 (2026-08-25验证)

**问题**: QuadRemesher全局自动布线不会为眼窝rim（眼睑开口边缘）这种小尺度精细特征让路，低模rim磨圆、无折角，眼睛显瞪。

## 定案方案：低模rim倒角 ✅（唯一有效）

1. `me.attributes.new("bevel_weight_edge", type='FLOAT', domain='EDGE')` 创建边属性
2. **直接用 `me.edges` 循环设 `bw_attr.data[e.index].value=1.0`**（rim±3mm内的边）
   - ❌ 不要用bmesh设属性：`bm.edges` 的 index 与 to_mesh 后的属性索引对不上，全为0
   - ❌ Blender 5.1 无 `BMEdge.bevel_weight` 属性，直接赋值报AttributeError
3. Bevel修改器：`limit_method='WEIGHT', width=0.0005(0.5mm), segments=2`
4. **应用倒角后再做UV**：UV展开会重建mesh、丢bevel属性。顺序 = 倒角→modifier_apply→Smart UV→烘焙
5. 验证: 渲染rim特写，vision确认折角明显、有厚度感

## 已试无效的方案（勿再试）

| 方案 | 结果 |
|---|---|
| rim边标记锐边（e.smooth=False） | 无效，rim面太少折角做不出来 |
| 局部subdivide加密 | 布线报废：碎面/三角面/极点，用户否决 |
| QR UseMaterialIds=1（rim材质边界引导） | rim锐利但几何粗糙：锯齿/撕裂碎块 |
| 高模rim预倒角0.3mm再QR | 无效，AutoDetectHardEdges检测不到小倒角 |
| 手动rim环+Bridge Edge Loops | 闭环但突兀生硬，与皮肤无过渡 |
| QR GuidesFile曲线引导 | QR 1.0曲线引导是WIP未实现（官方文档确认） |
| 烘焙法线贴图弥补 | 烘焙参数调大引入噪点，rim仍模糊；烘焙无法替代几何 |

## 判断基准

- 决定眼球外观的是**开口边缘带**（rim±3mm），不是碗内深处（被眼球遮挡）
- 低模rim带偏差<0.7mm、眼睑缘最前位置保持±1mm内 = 眼窝数据没丢
- 用户验收线：低模上眼睛不能"瞪"，眼睑要有包裹感（低模面数限制下靠倒角折角近似）
