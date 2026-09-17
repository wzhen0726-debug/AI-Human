# 演示版终端控制端 — 录屏汇报用管线复刻 (2026-09-04)

> 场景: 用户要录屏给领导汇报, 需要一个终端控制端, 输入命令(01/01a/02/03/04/05)就在对应输出文件夹真跑该环节。
> 产物: `Hermes/SZRYanJiu/演示版_终端控制端/` (独立目录, 不影响正式交付)。
> 入口 `控制台.py`, 命令: 01 / 01a / 02 / 03 / 04 / 05 / all / status / quit。

## 用户明确偏好(照做)
- **真跑, 不模拟**: 每个命令真实调用 Blender 处理, 不是刷假进度。用户主动选了"真跑"而非"演示模式"。
- **输出大量真实数字显得专业**: 终端实时滚动顶点数/面数/进度百分比/对称性/贴地检测等处理数据("显得高级")。控制台过滤纯噪声行(寄存器/插件警告), 突出数据行, 用颜色区分正常/错误/完成。
- **不影响现有交付**: 演示版建独立同级目录, 完整复制一份管线, 绝不改 `v3_QuadRemesher_交付/` 里已验证的内容。
- **命令驱动**: 用户输入 `01` 就输出01, 输入 `01a` 就输出01a。按环节顺序, 支持 `all` 全流程 + `status` 查产物。
- **产物落输出文件夹**: 每个环节跑完把产物复制到 `0X环节名/输出/`, 录屏时可见文件生成。
- **录屏前可清空**: `.gitignore` 排除大体积产物/工作区(可重新生成), 只提交控制台+README。录屏前可清空输出文件夹保持"从0开始"效果。

## 含手动打点的环节 — 控制台必须编排进去(易漏!)
01a 和 05 不是纯自动, 中间有**半自动手动打点**(用户GUI微调点位), 复刻管线时极易漏掉直接跑自动版 → 结果错。
- **01a 眼裂轮廓打点链**: `place_eyelid_markers.py`(右眼自动放12点) → **GUI手调** → `mirror_markers.py`(镜像右→左) → `read_eyelid_markers.py`(读点+Catmull-Rom样条加密72点轮廓json) → `run_eye_socket.py`(眼窝) → `run_eyeball_v2.py`(眼球) → `rim_pre_sharpen.py`。眼窝和眼球都基于手动轮廓json定位。
- **05 关节打点链**: `step1_ai_markers.py`(ARP AI自动打17关节) → **GUI手调** → `step2_go_detect.py` → `step3_to_7` → `normalize_rest.py` → `retarget_mixamo.py`。
- **控制台编排GUI暂停**: 自动打点后 `subprocess.run([BLENDER, blend])` 开GUI(非`-b`), 阻塞等用户调点关窗, 关窗即返回继续。打点前用 `os.startfile(md)` 弹出点位说明(05弹《点位指南.md》)。设 `DEMO_SKIP_GUI=1` 环境变量跳过GUI(仅自动化测试用, 正式录屏别设)。

## v2 UX(用户明确反馈, 照做)
- **进度提示**: 运行时终端必须有动静, 否则用户判"卡住"(静默计算段如黏连修复~70s最易误判)。用**单行动态进度**: 旋转符+进度条+百分比(能解析到QR等真实%时显示)+已用时间+实时阶段名, `\r`原地刷新不刷屏; 详细数据写日志文件。
- **防止终端滚动过多**: 每环节开始**清屏**(`cls`), 整屏只显示当前环节进度, 结束打印精简摘要框(标题+✓/✗+用时+关键数据)。历史靠 `logs/` 回看。
- **过滤插件噪声**: Better FBX 后台注册报 `bpy_types` ModuleNotFoundError 的红色Traceback 与管线无关但录屏扎眼 → 累积Traceback块, 判定含 `bpy_types`/`better_fbx` 则丢弃, 真实报错照常显示; 日志文件保留全部。

## 搭建步骤(可复刻)
1. **镜像交付结构**: 在演示目录内建 `交付/01高模修复与黏连检测/{scripts,models}` … `交付/05骨骼绑定/ARP新版测试_20260831/scripts` 等同款子目录(脚本路径常量是按这个结构写的)。
2. **复制脚本**: 从正式交付复制各环节脚本到对应 `交付/.../scripts/`。
3. **批量改写路径**: 写 `fix_paths.py` 用 `str.replace` 把脚本里所有硬编码的正式交付根路径 + 原始模型路径批量替换成演示目录路径。跑完 `grep -rnE "原始模型|v3_QuadRemesher_交付" 交付/ | grep -v 演示版` 确认零残留。
4. **复制预资产**到 `原始文件/`: Tripo高模GLB、眼球GLB、Mixamo动画FBX×4(Walk/Run/Jump/T-Pose)、眼位检测JSON(3ddfa×3)、修复贴图。以及交付结构内的 `01A眼窝与眼球/screenshots/3ddfa/*.json`。
5. **写 `控制台.py`**: 命令循环 + 每环节一个函数 + `run_blender()`(流式读子进程stdout实时打印) + `deliver()`(复制产物到输出) + `status()`。
6. **逐环节真跑验证**: 从01到05依次 `printf "01\nquit\n" | python 控制台.py`, 每个都要端到端通过才算完。别只测控制台能启动。
7. **提交**: 加 `.gitignore` 排除产物/工作区, 只提交控制台+README+脚本。

## 踩坑(本会话实测)
- **按权威流程复刻, 不要按文件名猜**: 重建管线时读了README/记录文档确认每环节的**正确脚本版本和打点链**, 别按环节名拼显而易见的脚本。本会话错用了旧眼球脚本`run_eyeball.py`(eye_01.glb)而非定案的`run_eyeball_v2.py`(Eye.fbx/眼睛模型002), 且整个漏了01a手动打点链 → 用户让"好好查查"。多个`_v2`/旧版共存时, README的"主要脚本"表是权威。
- **换眼球模型用预制FBX比append blend干净**: `Eye.fbx`(单只眼已合并的单mesh, 瞳孔朝-Y, 贴图已接) 优于 `Eye.blend` append三部件(虹膜/巩膜/阴影)再join。导入FBX后**用对象集合差集识别新增**(before/after `bpy.data.objects.keys()`), 只留名字以`Eye`开头的MESH, 删Camera/Cube/Light等FBX带入的垃圾; 第二只眼导入名会变`Eye_Iris.001`故用`startswith('Eye')`不用精确名。05并眼球筛选`startswith('Eye002')`, 故v2必须把眼球命名为`Eye002_L/R`才能被下游命中。
- **前台超时会留孤儿子进程**: 长管线(>600s)用 `background=true` 跑; 前台命令超时被杀后, 子Blender进程成孤儿仍在跑但stdout管道已断→日志冻结不可信。清理孤儿用 `MSYS_NO_PATHCONV=1 taskkill /F /IM blender.exe`(git-bash会把`/F`当路径转换, 必须加`MSYS_NO_PATHCONV=1`)。别启新进程跟孤儿抢同一产物。
- **`run_all.py` 的脚本路径**: 脚本都在 `scripts/` 子目录, 但 `run_all.py` 原代码用 `os.path.join(BASE, script)` 少了 `scripts/` → 复用到演示版必须改成 `os.path.join(BASE, 'scripts', script)`(否则找不到脚本)。qa 调用同理。
- **`mixamo_rest_spec.json` 缺失**: step3 `align_roll` 依赖 `_工作区_过程文件/logs/mixamo_rest_spec.json`, 该文件在正式交付的 `_工作区_过程文件/` 里, 默认不会随脚本复制 → 步骤4会静默崩溃(无Traceback直接Blender quit)。必须手动 `cp` 到演示目录的 `交付/05骨骼绑定/_工作区_过程文件/logs/`。
- **`logs/` 目录要先建**: 控制台把子进程日志写到 `logs/`, 后台进程若 `logs/` 不存在会启动即失败(报 No such file or directory)。复跑前先 `mkdir -p logs`。
- **run_repair.py 传参**: 支持 `blender -b --factory-startup --python run_repair.py -- <input.glb> <output.blend>` 传参, 演示版用它指定演示目录的输入输出(而非默认路径)。
- **`2>nul` 坑**: 后台/演示脚本禁用 `2>nul`(会创建Windows保留名nul文件, 难删且卡git)。错误落盘到具体日志文件。
- **Blender脚本returncode可能为0但实际失败**: 必须校验完成标记(如 `STEP1_DONE`/`UV_DONE`/`NORMALIZE_DONE`/`RETARGET_DONE`)才算真成功, 不能只看 exit code。

## 各环节实测耗时(本模型, 供录屏预估)
01修复~2.2min · 01a眼窝眼球~5.1min · 02QR拓扑~1.5min · 03UV~0.1min · 04烘焙~0.5min · 05绑定动画~6min(含AI打点) · 全流程all~16min。
