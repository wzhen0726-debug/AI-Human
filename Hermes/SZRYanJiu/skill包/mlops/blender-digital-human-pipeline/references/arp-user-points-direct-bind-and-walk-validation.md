# ARP 用户点位直建骨架 + 行走动画验证 (2026-08-27)

05骨骼绑定阶段 ARP 版第二次返工的完整教训。背景：用户要求 ARP 半自动打点（打开模板→自己摆点→保存→agent 跑剩余），第一版走 ARP Smart 自动流程产出骨架与模型完全错位（手腕差 32cm），第二版改为绕过 ARP Smart 直接用用户 17 点建标准 Mixamo 52 骨后毫米级吻合。

## 用户协作规范（一级信号，先读）

1. **一次只交一步、且必须是自查过的产物。** 用户原话："一次做的怪多，然后第一步 绑定就有问题，或者我帮你查，你做好了绑定先给我，我先看。也快"。含义：跑完绑定→立刻用数据自查关键骨头尾位置→确认无误→只交付这一个文件让用户检查→等确认再继续下一环节。禁止连续跑完 绑定→去控制器→导出GLB→渲染 一整串后才汇报。
2. **用户自己摆的点不许代摆。** 用户原话："我不需要你自动放好，我就是要测试从0到有，让我自己摆"。模板里可以给几何换算的预置参考值当对照，但正式流程是空场景+N面板工具按钮，用户光标放点。用户测试的是流程本身。
3. **自查脚本里的参考值必须来自当场 dump，不得手填旧值。** 本次验证脚本里手填了上一版推测的肩肘腕坐标，导致新绑定被误判"差17cm全错"，实际逐项≤1mm 全对。教训：写 verify 脚本时先用 blender -b --python-expr 从源文件 dump 用户实际点位 JSON，再比对。

## ⚠️ bpy.ops.object.add 在 3D 光标处创建 —— 整架平移大坑

- 现象：Hips 与用户点差 17.5cm、全身关节同向偏移约 20cm。
- 根因：`bpy.ops.object.add(type='ARMATURE')` 在 3D 光标当前位置创建对象。用户刚在 GUI 里打过点，光标停在 (0.143, 0.006, 0.101)，整个骨架坐标系被平移了这段距离（armature 对象 location ≠ 原点）。
- 修复：创建前必须 `bpy.context.scene.cursor.location = (0, 0, 0)`（Blender 5.x 属性名是 `scene.cursor.location`，不是旧的 `scene.cursor_location`）。
- 附带诊断技巧：怀疑整体平移时，对比 `arm.matrix_world.translation` 是否非零 / `a.location` 是否等于某个可疑的旧光标值。

## 为什么绕过 ARP Smart（保留供取舍判断）

即使用户已把 17 个标记写入 guess_markers 生成的 `_loc/_sym` 对象，ARP Smart 后台跑完仍按其默认模板比例长骨（手腕差 32cm），并留下：(1) 348 根 c_*/root_*/ik 机制骨淹没变形骨；(2) 50+ 个 cs_* 控制器形状网格垃圾；(3) 用户的标记球全部残留；(4) armature 对象带 0.9794 缩放；(5) 手指引擎默认 AI 模式找 thumb1_loc 崩溃（需设 LEGACY 才能跳过）。结论：**点位驱动绑定时不用 Smart 生成步骤，只用它对齐命名之后的产物或干脆直建**。

## 直建方案A管线（复用手写版已验证代码）

1. 输入：用户点（ARP 命名 `NN_中文[_对侧镜像]`，主侧 +X）→ 映射为 crotch/chin/neck/shoulder/elbow/wrist/thigh_top/knee/ankle。
2. 左右映射铁律：模型面朝 −Y 时，**+X 是角色左臂方向 = Mixamo Left 系**。用户"右肩"类直觉标记在 +X 侧要建成 Left 骨，否则行走动画左右镜像。左手 side_off 要取反（手指沿掌宽镜像），否则左右手指交叉错位。
3. 朝向：每骨 tail/head 方向照抄 `logs/mixamo_rest_spec.json`（T-Pose.fbx 实测的世界系 y 轴+z 轴 per bone），`b.tail = b.head + y_dir*len` 后 `b.align_roll(z_dir)`。验收=静止姿态逐骨对照方向差/roll 差 0.00°。
4. 权重：ARMATURE_AUTO 私有顶点组后校验覆盖 100%；眼球（Eye002_L/R 无权重小网格）用 BONE 父级绑 Head 骨，父级矩阵=head_b.matrix_local @ Translation((0,length,0)) 的逆作用原世界矩阵（只换算位置会瞳孔朝下——旋转也必须保留）。

## 行走动画不生效的三层排查链（手写版踩实）

现象"动作只在参考模型上/我的模型不动"，逐层：
1. **slot 错绑**：animation_data.action_slot 的 handle 指向空 slot，而 fcurves 全在另一 slot 的 channelbag 里（本例 143 空槽 vs 142 数据槽）。修复：改绑到装有数据的 slot。Blender 5.x API 速记：`strip.channelbags` 是**属性**（带 s，不可调用）；ActionSlot 没有 `.name` 用 `.identifier`；`action.fcurves` 在 5.x 不存在。
2. **混入参考模型**：walk 测试文件里残留 Alpha_Joints/Alpha_Surface/65 骨参考骨架，视觉上"动作在别人身上"。删除即可。
3. **验证必须用求值网格**：`body.data.vertices` 是原始数据永远显示 0 变形；要用 `depsgraph.evaluated_get(body)` 取 evaluated mesh 比帧间顶点位移（本例 1952/2000 顶点在动）。之前几十轮"重跑无效"全是因为验证方法本身错了。

## 变形骨清理用白名单，禁用前缀过滤

godot 导出清控制器时，`startswith("mixamorig:")` 过滤曾把 arp_to_mixamo 重命名后的 55 根变形骨**全删成空骨架**（它们没有前缀）。改用 Mixamo 标准 52+端点名白名单保留；bend/spine 特殊骨权重迁移到 Mixamo 脊柱再删；孤立顶点组顺手清掉。验收：骨骼数==顶点组数==关键样本骨权重>0。

## 交付物形态

- 逐步检查文件放 `ARP版交付/NN_中文.blend`；过程脚本/日志进 `_工作区_过程文件/`（根目录只留 README+交付文件夹，见 rigging-folder-organization.md）。
- 行走演示要渲染成 **MP4** 放交付目录（FFMPEG/H264，24fps，正面机位 y=-3.2 z=0.95 rot=(90°,0,0)，EEVEE），只在 blend 里给测试文件不算"看到了行走文件"。
