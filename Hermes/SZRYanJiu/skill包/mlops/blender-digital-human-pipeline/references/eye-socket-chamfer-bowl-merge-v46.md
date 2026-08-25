# 眼窝 M 形环线: 根因与合并环方案 (v46g→v46i)

## 问题
眼窝线框里出现明显的 M 形/双环分界线(眼窝缝倒角带与内部碗面之间),
内部面分布与倒角带完全不同, 环线在交界处密集。用户多次反馈"这明显不对"。

## 走过的弯路(按序)
1. **v46f** quintic smoothstep 平滑倒角过渡 → M线仍在。
2. **v46g** 碗面从极点三角扇改为环形网格+小圆盘封底 → 极点收敛消除, M线仍在。
3. **v46h** 动态倒角参数(按眼窝大小算) → 布线整体均匀了, 但 M 处仍有两条紧贴的环。

## 根因
M 线不是倒角参数问题, 而是**结构分界**: 倒角带(chamfer band)与碗面(bowl)
是两段分别构建的面带, 在中间环 `ring1` 处拼接。拼接环在曲面上形成可见的
分界环线(两侧面分布/密度不同)。调参只能改带宽, 消不掉接缝。

## 修复 (v46i): 合并倒角带+碗面为一条连续环序列
从 rim 边界环 `ring0` 直接生成全部环, 不再有中间 `ring1`:
- 前 `F` 环 = 倒角段 (`CHAMFER_FILLET_RINGS = 8`)
- 后 `NR` 环 = 碗面收缩段 (`NR = 16`, 起始收缩率从 0 连续增长)
- 碗底用小圆盘三角封口
- 全程同一套环索引连续生成 → 无拼接环 → 无线框分界线
结果: L 眼 2100 面 (24 rings × 84), R 眼 1850 面 (24 rings × 74), 线框验证 M 线消失。

## 动态倒角参数 (替代固定 3mm)
`eye_socket_config.py`:
- `CHAMFER_WIDTH_RATIO = 0.20` (倒角宽 = 0.20 × 眼窝 rim 平均半径)
- `CHAMFER_DEPTH_RATIO = 0.50` (倒角深 = 0.50 × 倒角宽)
- `CHAMFER_FILLET_RINGS = 8`
实测: 眼窝 35.1×12.2mm, avg rim 半径 11.8mm → 倒角宽 2.36mm、深 1.18mm。
固定 3mm 对 35mm 宽眼窝比例失调。

## 合并后完整性验证(用户硬性要求: 焊接完整/无破面/无游离点)
`scripts/check_mesh_integrity.py`(本skill scripts/下有通用版) 检查:
- 游离点: 不属于任何面的顶点
- 未焊接重复顶点: grid hash (round 3位) 检测同位多顶点
- 退化面: area < 1e-12
- 非流形边: 内部边被≠2面共享 (碗底极点处 3+ 面共享属正常结构)
- 边界边: 只应存在于 rim 外缘与高模接缝处

## 坑: Blender -b 静默退出无 traceback
重构 socket_ops.py 合并逻辑后, 后台 Blender 进程 exit 0 但:
- `01_1_eye_socket.blend` mtime 未变(还是上一版), 日志无 `Saved:`
- 日志停在重构点(如"合并环: 2100 faces...")后直接 `Blender quit`
根因: 重构后残留对已删变量的引用(`chamfer_faces`)或未定义变量(`ring0_coords`),
异常被 Blender 吞掉无 traceback。
诊断套路: ① 看日志有没有 `Saved:` ② 看 blend 文件 mtime ③ grep 重构中删掉的
变量名还在哪里被引用, 逐一补齐定义/删引用。

## 线框渲染验证法
`render_wireframe.py`: ShaderNodeWireframe(Size=0.0005) → Emission 黑色,
白色 world, EEVEE, 相机对准眼中心(85mm)。渲染后用 vision_analyze 判断
M 线有无/布线是否均匀(灰模阶段不可靠, 必须带线框材质渲染后再问 vision)。
