# 蒙皮绑定核验: 顶点组名 ⇄ 骨名 / 活体探针

适用: 任何"骨骼驱动网格"的环节(眼球/身体/道具)。本管线 05 链 = step3(ARP绑定) → 03B(标准化) → retarget(前缀统一) → 04(动作)。

## 铁律 1: 顶点组名必须与骨架骨名逐字一致

Armature 修改器按【名字】匹配顶点组; 名字错配 = 该网格静默不动(无报错)。骨名前缀随阶段变化
(ARP 绑定后无前缀 `Head`; retarget 统一加 `mixamorig:`), 所以:

- 建/改顶点组时**从骨架实取骨名**, 不硬编码:
  `hb = next(b.name for b in arm.data.bones if b.name.split(':')[-1].lower() == 'head')`
- 顺手清掉与骨名不符的历史组; 已有 ARMATURE 修改器但 `m.object` 不是本骨架也要纠正。
- **改名骨头的脚本必须同步改名顶点组**(去前缀同义映射, 防御式): retarget 已内建
  (`if vg.name not in boneset and PREF+vg.name in boneset: vg.name = PREF+vg.name`); 03B(normalize)存档前也加同义同步作双保险。

## 铁律 2: LBS 自查通过 ≠ 能动

几何层(LBS 数学, 常写成"容忍前缀"的映射)与名字层(Armature 修改器实时匹配)是**两套真值**。
自查全绿仍可能"用户在 Blender 里动骨骼、网格不动" —— 实测眼球在 03/03B 位移 0.00mm 而所有自查通过,
只有 retarget 加前缀后才碰巧对上(所以只有 04 跟随)。**不要拿"容忍前缀的解析函数"当名字已对齐的证据。**

## 铁律 3: 物体级跟随 = 必须【父级到骨架物体】(只有修改器不够)

ARMATURE 修改器只承载【骨骼形变】, **不含骨架物体自身的位移**。只挂修改器、没有父级的网格:
物体模式移动骨架 1m → 该网格 **0.0mm 不动**(而骨骼层面转骨/动骨仍会响应 → 表现为"有一点点移动",
极易被误判成"跟随正常")。身体跟随是因为绑定流程给它加了父级; 眼球是后加的独立对象, 最容易漏父级。修法(保持世界位置):

```python
if o.parent is not arm:
    o.parent = arm
    o.parent_type = 'OBJECT'
    o.matrix_parent_inverse = arm.matrix_world.inverted()   # 抵消父级变换, 世界位置不变
```

已有 ARMATURE 修改器但 `m.object` 不是本骨架的, 顺手纠正目标。父级 = 物体级位移, 修改器 = 骨骼级形变,
**两层都要, 缺一即"动骨架不跟随"**。

## 验收 = 两层活体探针(物体级 + 骨骼级), 不是看权重组

```python
# 对每个产物 blend: 转 Head 骨 10° → depsgraph 求值 → 测各蒙皮网格顶点位移 (只读, 不保存)
import bpy, math; import numpy as np
bpy.ops.wm.open_mainfile(filepath=P)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
hb = next((b.name for b in arm.data.bones if b.name.split(':')[-1].lower() == 'head'), None)
def ev(ob):
    dg = bpy.context.evaluated_depsgraph_get(); e = ob.evaluated_get(dg); m = e.to_mesh()
    a = np.empty(len(m.vertices) * 3); m.vertices.foreach_get('co', a); a = a.reshape(-1, 3)
    e.to_mesh_clear(); return a
if hb:
    targets = [o for o in bpy.data.objects if o.type == 'MESH' and any(x.type == 'ARMATURE' for x in o.modifiers)]
    before = {o.name: ev(o) for o in targets}
    pb = arm.pose.bones[hb]; old = tuple(pb.rotation_euler); pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (math.radians(10), 0, 0); bpy.context.view_layer.update()
    for o in targets:
        d = np.linalg.norm(ev(o) - before[o.name], axis=1)
        print(f"{o.name}: 位移 max {d.max()*1000:.2f}mm")   # 0.00mm = 名字没对上
    pb.rotation_euler = old
```

对 03(未标准化)/03B/04 每个产物都跑; 修好后应同量级跟随(本管线实测 29 / 29 / 40mm)。

**必须两个探针都做**(骨骼级探针单独会漏):

- **物体级**: `arm.location.x += 1.0` → 所有蒙皮网格(含眼球)应位移 **1000mm**; 出现 0.0mm = 缺父级(铁律 3)。
- **骨骼级**: 转 Head 10° → 同量级跟随(上表)。

实测教训: 骨骼级探针全绿(29mm)时物体级仍是 0.0mm —— 用户验收方式正是
"选中骨架, 物体模式移动 1m", 所以两层必须都量、都报给用户。

## 修复位置(本管线, 已应用)

- **骨架在哪个环节创建, 就在那个环节给产品网格补父级**: `step2_go_detect.py` 生成骨架后立即把 身体(顶点数最大的网格)+眼球 父级到骨架, 并打印世界位移(应≈0)。**每个中间产物文件都要成立** —— 用户会在任意环节的大纲里检查"网格是否挂在骨架之下", 中间件里网格悬在 Collection 根下会被当场点名(网格归属 = 用户的第一步验收)。已存在的中间件用一次性手术补齐(只动网格对象本身, 不碰手调文件); 尚无骨架的前置环节(如 04 烘焙)不存在此问题, 别去"修"。
- `step3_to_7_rig_and_walk.py`: 眼球顶点组名 = 实际 Head 骨名 + 清杂组 + 纠正修改器目标 + **补父级到骨架物体(铁律 3)**
- `normalize_to_tpose.py`: 存档前"顶点组名⇄实际骨名"同步(前缀不敏感)
- `retarget_mixamo.py`: 防御式前缀同步(保持)
