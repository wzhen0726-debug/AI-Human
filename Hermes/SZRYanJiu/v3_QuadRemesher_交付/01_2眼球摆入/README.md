# 01_2 眼球摆入

> 状态：⚠️ 脚本已就位，但**摆放参数未定案，未通过验收**（视觉检查报眼球过度前凸，详见 `方案md记录/v3_QuadRemesher/08眼窝与眼球集成/问题分析_眼球摆入.md`）。

## 位置
01_1眼窝制作之后。眼球是独立物体，**不进 02 QR / 03 UV / 04 烘焙**，只在 05 绑定、06 导出时并入。

## 功能
- 导入 `eye_01.glb`，按 x 坐标拆成左右眼（GLB 命名与位置相反：Eye_L 实际在右、Eye_R 实际在左，脚本按位置分配，不依赖名字）
- 摆入眼窝：球心 = 开口中心沿全局前向(-Y)内缩 `EYE_PUSH_IN`；朝向 = 局部+Z(瞳孔)对准全局-Y（平视）
- 强制贴图显示：Image Texture 直连 Base Color（绕过 Mix）
- 保存 blend + 渲染正面/侧面/特写验证图

## 输入
- `01_1眼窝制作/models/01_1_eye_socket.blend`
- `原始模型/Metahuman低模/眼睛模型001/eye_01.glb`（双眼各802顶点/1536面，直径约29mm，自带1024贴图）

## 输出
- `models/01_2_eyeball_placed.blend`
- `screenshots/01_2_eyeball_{front,side,close}.png`

## 参数（scripts/eyeball_config.py）
- 开口中心 L/R：实测值（比虹膜中心略靠外）
- `EYE_SCALE = 1.0`（先不缩，渲染定夺，备 0.85-0.9）
- `EYE_PUSH_IN = 0.022`（22mm，当前值，未定案）
- `PUPIL_LOCAL_DIR = (0, -0.04, 0.997)`（瞳孔=局部+Z，实测）

## 运行
```bash
cd scripts
"D:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python run_eyeball.py
```

## 验收标准（未达成）
- 侧面看：眼球下半部被开口边缘遮挡，角膜探出量 3-5mm，不穿出眼睑皮肤外侧
- 正面看：双眼视线平行朝前（平视），眼皮压住眼球，不过凸/不内陷
