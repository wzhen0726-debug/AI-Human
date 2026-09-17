# ARP 标记点驱动绑定 — 2026-09-01/02 重跑经验

> 配套脚本: `v3_QuadRemesher_交付/05骨骼绑定/ARP新版测试_20260831/`
> 管线入口 `run_all.py`(step1→2→3-7), 自检 `qa_rig.py`/`qa_walk.py`/`check_markers.py`

## 核心路线(定案)
位置 = ARP 参考骨(`_ref`后缀, T-pose贴合模型), 朝向 = align_roll 对齐 Mixamo spec 的 z 轴。
用户标记点: 校验 + 关键关节(肘/腿)直接按点定位。

## 本次踩坑(血泪)

### 1. 读带约束的对象位置 — 必须 matrix_world.translation
标记点 `_sym` 靠 COPY_LOCATION 约束(invert_x)镜像跟随主点。
- ❌ `obj.location` = 约束**前**的局部值 → 读到假的不对称, 误以为要打点不对称
- ✅ `obj.evaluated_get(dg).matrix_world.translation` = 约束**后**的真实镜像位置(严格对称)
- library_load 读的对象未 link 场景时 matrix_world 是单位矩阵(全0) → 必须先 link + `view_layer.update()` 再读

### 2. ARP 肘关节不是用户的点
go_detect 内部"肘朝向修正"会把 forearm_ref.head 旋转偏移(我们的点被压2.5cm)。
用户打的 elbow_loc 只被设为大臂 tail。→ 建骨后把 LeftForeArm.head 对回 elbow_loc。

### 3. Hips 垂直起伏不能删
行走动画 Hips location 三轴删除会导致双脚腾空+滑步。
- Hips 局部 **y 轴 = 世界垂直**(已实测, 不是z轴)
- 恢复方法: 逐帧读参考骨架 Hips 世界z, 按腿长比(实测)缩放, 写入我们 Hips `pose_bone.location.y` + keyframe_insert
- 腿长比 = (我们Hips_z - Foot_z) / (参考Hips_z - Foot_z), 全部实测不写死

### 4. 骨骼轴向要实测, 不能假设
参考骨架(Mixamo FBX): Hips 局部 y=垂直, 单位cm(scale 0.01)。
我们骨架: Hips 局部 y=垂直, 单位m(scale 1)。轴向相同但单位不同, 位移要换算。

### 5. 用户打点原则(用户强调)
"点打在哪骨骼就在哪, 不要自己改成解剖位置"——用户可調点来改变骨骼。中心化/解剖修正要先问用户。
大腿根 Hips 起点应在骨盆上缘(高于胯点 thigh **6-10cm**, 该模型实测10.4), 不是会阴/大腿根同高。
自检脚本参考值必须随打点决策同步更新(否则自检永远报错), 见 `pipeline-delivery-audit.md` 第4节。

### 5.5 管线重跑保护
step1 AI打点重跑会覆盖用户手调的01点位文件 → 重跑前必须自动备份(带时间戳)。已实现在 step1 里。

### 6. 硬编码参数化(跨体型)
所有体型相关数值按身高/bbox 比例算, 不写死:
- 黏连判定距离 = 身高mm/360, 推开步长 = threshold/10
- 焊接距离 = 身高/18000(0.1mm@1.8m)
- 排除区(手腕|X|/脚踝Z) = 身高×0.233 / ×0.056
- 烘焙 cage/ray = bbox_max×0.011/×0.056
- 退化面/碎面面积 = ×(身高/1.8)²

### 7. Windows 保留名坑
`2>nul` 在 git-bash 下会创建真实文件 `nul`(Windows保留名, 难删)。
删除: `os.remove("\\\\?\\" + 完整绝对路径)` (扩展路径前缀)。
后台脚本禁用 `2>nul`, 错误必须落盘到具体文件。

## 验收标准
- qa_rig: 55骨、24对全对称、0断链、权重55组、无零长度骨
- 行走: PASS、贴地0腾空、Hips起伏2-5cm

## 眼球并入(绑定阶段) — 2026-09-03 血泪修正
眼球独立物体不进QR/烘焙(01A设计), 在绑定阶段从 `01A眼窝与眼球/models/01_2_eyeball_placed.blend` link 入 Eye002_L/R。

**❌ 错误做法(会导致眼球飞头顶)**: bone parenting (`parent_type='BONE'` + `matrix_parent_inverse`换算) 或 Child Of 约束——坐标系换算复杂且易错, 眼球会被放到 Head 骨局部系偏到头顶(z=1.9)。

**✅ 正确做法(顶点蒙皮, 简单可靠)**: 给眼球对象加顶点组指向 `mixamorig:Head`(权重1.0) + Armature修改器指向骨架。眼球顶点不动, 只是被 Head 骨带着旋转, 世界位置不变。代码:
```python
vg = eye_obj.vertex_groups.new(name='mixamorig:Head')
vg.add(list(range(len(eye_obj.data.vertices))), 1.0, 'REPLACE')
mod = eye_obj.modifiers.new('Armature', 'ARMATURE')
mod.object = armature
mod.use_deform_preserve_volume = True
```
验证: 绑定后眼球世界位置应与原始位置一致(差<1mm)。

## 多动画适配(2026-09-03/04 定案)
不同Mixamo动画的参考骨架腿长不同(Walk 0.893m, Jump/Running 0.955m)——不能用同一腿长比。每个动画独立从它自己的参考骨架实测算腿长比。贴地检测要区分"离地期(跳/跑正常腾空)"和"支撑期错误腾空"——支撑期判定=参考骨架该帧脚底<0.15m时我们也必须贴地。

### Rest姿态差异 → 腿外八/动作古怪(用户报"走路外八/跑步腿古怪") — 2026-09-04定案
我们骨架rest=模型自然站姿(腿分开), Mixamo参考rest=T-pose(腿并拢), 同名骨rest朝向实测差: 本模型平均11.9°(拇指34.7°/颈21.8°/肩17.3°/腿8°)。

**✅ 定案方案(用户指定: 先把骨骼改成跟Mixamo相同, 再绑动画)** — 测量驱动、无硬编码:
1. `normalize_rest.py`: 把骨架每根骨rest朝向改成Mixamo标准(锚用户提供的T-Pose.fbx, 目标朝向 = 我们Hips朝向 @ (参考Hips朝向^-1 @ 参考骨朝向)), **只改朝向不动骨头位置**(保持打点位置与角色形状, 实证头位置/网格均0位移)。差异全实测(阈值>0.5°才改)——下个模型若rest本就标准, 差异≈0自动跳过。产 `03_mixamo_rest.blend`。
2. `retarget_mixamo.py`: rest一致后直接复制参考动画action(局部旋转通道精确生效), 只重建Hips垂直起伏(参考世界z变化×实测腿长比, 写入数值探测的垂直轴)。帧数完全按参考动画原始范围, **不铺周期/不加循环加工**。
3. 每动画独立实测腿长比(参考骨架比例不同: Walk 0.893m / Running+Jump 0.955m, 本例0.963/0.900/0.900)。

**关键实测事实**:
- Mixamo三个动画FBX的rest姿态完全一致(0.00°差)且=用户T-Pose.fbx → 一次归一化通用; 三参考骨架仅比例不同。
- 参考骨架matrix_world带0.01缩放(厘米单位): 算相对变换必须**平移向量+四元数分开算**, 不能用`H_r.inverted() @ ref_w[bn]`矩阵逆(混入局部厘米值→87m偏差)。
- normalize_rest编辑模式改朝向前必须断开全部连接骨(use_connect), 否则旋转父骨拖动子骨头位置; 改完**不恢复**连接(恢复会把子骨头拖回父骨tail破坏打点位置)。改朝向的矩阵: `eb.matrix = Matrix.Translation(head) @ tgt_q.to_matrix().to_4x4()`(armature空间, 头位置不动, 实证子骨0位移)。
- Hips垂直轴探测必须在**无action时**做(有action时pb.location被fcurve覆盖, 探测读数全0)。
- ❌ 弃用`pose.armature_apply`改rest: 它会移动子骨头位置→骨架塌缩(腿长0.86m变0.033m)。
- ❌ 弃用逐帧世界旋转烘焙+CYCLES修改器: 用户明确"按我提供的mixamo去做, 他几帧你就几帧, 别乱改乱加东西"。
- 验证: 绑定后渲染三动作(走/跑/跳各抽帧)确认姿态自然无拧转; 数值看Hips起伏/腾空/脚底最低点。

### 循环动画的规矩(用户2026-09-04明确)
"他几帧你就几帧"——帧范围完全按参考动画原始action范围, 不铺周期、不加CYCLES修改器、不写死帧数。之前用户报"跑一半不循环"是用户自己播放器循环帧设置问题, 不是我们该修的。`rig_act.use_frame_range = True` 让切换动作时场景帧范围跟随。
- ❌ CYCLES修改器套四元数通道=分量当标量外推→肢体拧转(已验证是坑)。枚举名'CYCLES'不是'CYCLIC'。

### Blender 5.x 新动作系统合并多动作的坑(多动作入一个blend)
- `action.copy()` 与原件共享slot数据: 删参考骨架/原动作会**连锁删掉副本动作**。对策: 每个命名动作 `use_fake_user = True`; 先save_mainfile落盘保动作 → 再删 `Armature|...` 参考动作 → 再save; 删完断言三个命名动作仍在。
- 同一场景连续导入多个FBX: `next(o for o in bpy.data.objects if o.type=='ARMATURE' and o!=arm)` 会抓到**上一轮**的旧参考骨架 → 每处理完一个动画立即 `bpy.data.objects.remove(walk_arm, do_unlink=True)`。
- 套动画前骨名/顶点组 `mixamorig:` 前缀要和03保存时状态对齐(03保存时可能没前缀, 先补前缀再导入)。
- FBX导入报警 "新骨骼名称与现有顶点组名称冲突"(眼球蒙皮Head组) 无害, 可忽略。
- **FBX导入会带入参考人体网格**(Alpha_Joints/Alpha_Surface/Beta_Joints/Beta_Surface/char_grp/cs_*) 横躺场景挡视线。每处理完一个动画和每次自查导入参考后都要 `cleanup_ref()`: 删除所有非{骨架,身体,眼球}的对象。交付前断言场景对象只剩我们自己的。
- `bpy_types` ModuleNotFoundError(better_fbx插件) 是背景噪声, 不影响主流程。

## 交付前纪律(血泪)
绑定/模型改动后, 必须先渲染/数值验证再交付, 不能只报QA脚本PASS——QA脚本过≠视觉正常。用户抓到异常后, 先判断是源模型几何还是管线导致(例: 融合手是源模型自带, 手部y厚14.5cm三阶段未变=绑定无责), 再修。

## 交付文件夹整理规范(参考其他环节)
主产物 blend 放根目录; 脚本归 `scripts/`; 日志归 `logs/`; README 写产物+脚本+用法+关键规则; 删除一次性诊断脚本(diag_*)、Windows nul 保留名文件、.blend1 备份。git 提交时排除 logs/。

## 管线封装脚本坑(run_all.py)
- subprocess 封装脚本用法是 `python run_all.py`, 不是 `blender -b --python`(文档注释要写对)
- Blender 脚本异常时 returncode 可能仍为 0 → 不能只看 exit code, 要校验各步骤的完成标记(`STEP1_DONE`/`STEPS_3_TO_7_DONE` 等自定义打印)才算真成功
- 传参 `python run_all.py 2` 里 `--` 不是必须的, 遍历 sys.argv 找数字即可

## 改名同步纪律
重命名产物文件(如 04_行走测试→04_动作测试)后, 必须 grep 全目录把旧名引用全改(脚本/README/记录), 否则悬空引用。
