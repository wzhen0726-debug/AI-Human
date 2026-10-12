# 03 UV + 04 烘焙 重写经验 (2026-09-20)

## 对象选择陷阱
从02 QR blend加载时，必须**按名字后缀(_QR)选低模**，不能按顶点数选（`max(..., key=len(o.data.vertices))`）——03_auto_uv.blend可能因历史残留包含高模（96万顶点>低模16万），导致04把材质赋给高模、低模无贴图显示紫色。

**03脚本保存前必须显式删除非低模对象**：
```python
for o in bpy.data.objects:
    if o != low_poly:
        bpy.data.objects.remove(o, do_unlink=True)
```

**04脚本保存前也必须删除高模和眼球，只留低模**。

## 烘焙参数
- cage=0.01, ray=0.05, margin=16（固定值，不按bbox比例）
- bbox比例化（0.011×bbox, 0.056×bbox）会导致实际值翻倍，产生锯齿
- margin=32会导致texture_fix过度处理（64032→123000像素），产生大片粉色斑块

## 领口锯齿根因
02 QR低模领口边缘与高模有1-2mm系统性偏差，导致烘焙射线打到皮肤而非衣物。非UV布局或烘焙参数问题。需02 QR阶段改进或手动调整。

## 用户要求"重写"时的铁律
禁止参考旧脚本/旧文档/旧思路——复制旧代码会重复同样错误。必须独立调研当前最佳实践，从输入数据开始重新设计。

## 岛内自重叠/挤压松弛定案（2026-09-22，用户GUI圈出眼角/耳后/鼻翼重叠+挤压）
- 用户圈的不是岛间重叠（岛间=0.000%），是**岛内同向自重叠**（锥面总角>2π，angle-based不切缝必叠）+ 挤压sliver。旧03四项指标查不到→判据盲区。
- 检测: `self_overlap()` 双重覆盖栅格+重心坐标严格内部(>0.05排共享边缝)，不腐蚀；挤压=**逐面**UV面积/3D面积<0.1×中位（逐三角对quad误报：单三角退化但整面ratio 0.61~0.99，实测6例）。
- 修复两段式:
  1. Smart重切1轮: 重叠面+小岛(≤2000面)挤压→选区smart_project(66°)→average_islands_scale→全模型CONCAVE pack。850px→38px。
  2. **numpy平移pass** `fix_overlap_translate()`: 重叠簇上层片(o2)整体平移进UV空区(保密度=切一条缝)；挤压sliver按**整面**密度比精确放大(上限20x)再平移。38px→0。
- 坑(实测):
  - 多轮Smart重切必回归: 第2轮残留面重切+pack全局rescale → U崩12.7%/岛1154。逐轮回滚守卫(U<0.8×前轮 或 岛>1.5×前轮 → foreach_set恢复快照)。
  - 整岛重切(38974面)同样崩U。部分面重切(805面)才安全。
  - 回滚后**不能再调measure/self_overlap**(foreach_set后C层loop_triangles=ACCESS_VIOLATION崩溃)；且uvl指针在edit mode往返后失效，回滚必须重取`mesh.data.uv_layers.active.data`。
  - sliver按单三角ratio缩放对quad过冲16.8x→CV爆0.436；按整面ratio精确缩放→CV回0.110。
  - UV焊接=各面loop的UV值相等(非共享索引)，故平移/放大某面loops只断该面边界焊缝，不拉扯邻面。
- 验收: 重叠0px/挤压0面/CV≤0.11/密度比≤1/岛数比≤1.06 + 4K布局图头部岛vision确认无叠压无细条。
