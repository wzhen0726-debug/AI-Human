"""01A眼窝与眼球 - 眼窝配置参数

全部尺寸单位: 米(Blender内部单位), 注释给mm。
眼窝位置: 01高模修复之后、02 QR之前。
"""
import os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
# 测试阶段产物位置(用户约定 2026-09-09: 测试期产物写各stage的 输出/, 交付/ 只在定稿后整理)
WORK = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\01a眼窝眼球\输出"
os.makedirs(WORK, exist_ok=True)
IN_BLEND = os.path.join(r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端", "01高模修复", "输出", "01_highpoly_repair.blend")
OUT_BLEND = os.path.join(WORK, "01_1_eye_socket.blend")
SHOT_DIR = os.path.join(WORK, "screenshots")

# 3DDFA反投影结果 (精确定位眼部, 替代暗像素法)
DDFA_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "iris_3ddfa.json")
USE_3DDFA = True   # True=用3DDFA语义定位, False=回退暗像素法(已暂停)

# 虹膜中心 (实测, 脚本会重新自动检测校正)
IRIS_L = (-0.0241, -0.1163, 1.6517)
IRIS_R = (0.0229, -0.1168, 1.6507)

# 开孔椭圆尺寸 (半径): 宽26mm/2=13mm, 高18mm/2=9mm
HOLE_RX = 0.013   # 半宽 (内外眼角方向)
HOLE_RZ = 0.009   # 半高 (上下眼睑方向)

# 2026-08-07: 真实眼形=3DDFA眼睑轮廓(杏仁形26.8x9.7mm, 宽高比2.75, 两头尖).
# 之前的对称椭圆(rz=9mm)太圆太高, 宽高比仅1.44, 开出来像"球"不像杏仁.
# 2026-08-20: 3DDFA眼裂偏小偏上, 改用GUI半自动标记点提取的真实眼窝边界(eyelid_contour_manual.json)
EYELID_CONTOUR_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
EYELID_CONTOUR_3DDFA_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour.json")
USE_EYELID_CONTOUR = True   # True=用眼睑轮廓开孔(杏仁), False=回退对称椭圆

# 压凹范围与深度
SOCKET_RADIUS = 0.015   # 压凹影响半径 15mm
SOCKET_DEPTH = 0.010    # 最深 10mm
CUP_DEPTH_RATIO = 1.5   # 封碗底深度 = SOCKET_DEPTH * 此值 (15mm, 保证眼球后有封闭背景)
ENABLE_PUSH_IN = False  # 2026-08-07: 压凹是星爆源头(杏仁尖角顶点压得最深->锯齿). 关掉,凹陷由碗负责

# 平滑半椭圆碗 (make_eye_cup)
CUP_SEGMENTS = 32       # 经线段数(绕碗口, 越大越平滑)
CUP_RINGS = 16          # 纬线圈数(口沿->碗底, 2026-08-07: 8环坡度太陡, 增到16环平滑过渡)
CUP_DEPTH = 0.015       # 碗最深 15mm (2026-08-07: 20mm碗底y到+0.10穿进后脑壳, 减到15mm)
# ---- v60(2026-09-14) 碗深改按【眼球几何】反推, 替代上面固定15mm ----
# 实测(01_2): 眼球球心y=-97.3mm(=眼睑开口平面-108.4 + 角膜顶点距11.2 - 凸出0.1), 半径14.56mm(直径29.1mm).
#   旧碗底-93.4mm(15mm深) → 球后极-82.7mm戳穿碗底10.7mm; 且碗底仍在脸面基准(-82~-90mm)之前,
#   整个眼窝只是"骑在闭眼鼓包上的浅碟"而不是凹进脸里的坑(用户GUI截图所见"粉色圆盘叠在脸上").
# 新: 碗底 = 球心 + 球半径 + 2mm间隙 = 开口平面后 27.6mm → 碗底落到脸面基准之后 ✓ 且真正包住眼球.
BALL_CORNEA_DIST = 0.0112    # FBX眼球: 球心→角膜顶点距(01_2实测)
BALL_RADIUS = 0.01456        # 眼球半径(实测直径29.1mm; 与eyeball_config.EYE_RADIUS=0.0145一致)
BALL_PROTRUDE = 0.0001       # 角膜凸出开口平面量(=eye002_config.EYE_PROTRUSION_MM 0.1mm)
BALL_CUP_CLEARANCE = 0.002   # 碗底留给球后极的间隙
SOCKET_CUP_DEPTH = BALL_CORNEA_DIST - BALL_PROTRUDE + BALL_RADIUS + BALL_CUP_CLEARANCE  # ≈0.0276m

# 2026-08-20 v46h: 倒角参数根据眼窝大小动态计算.
# 根因: 固定3mm倒角带对35mm宽眼窝太窄, ring1处面分布突变→M形环线.
# 计算: 倒角宽度 = 眼窝平均半径的20% (35mm宽→avg半径17.5mm→倒角宽3.5mm, 上限6mm).
#       倒角深度 = 宽度的50% (保持弧度比例).
CHAMFER_WIDTH_RATIO = 0.20   # 倒角宽度占眼窝平均半径比例
CHAMFER_DEPTH_RATIO = 0.50   # 倒角深度占宽度比例
CHAMFER_FILLET_RINGS = 8     # 中间环数(增加让过渡更平滑)

# v47: M形凸脊消除两方案开关
# "no_chamfer"    = 方案A: 不倒角, 碗面直接从rim收缩下沉(无外扩段→无凸脊)
# "chamfer_relax" = 方案B: 保留倒角, 对眼窝内部环做Laplacian松弛磨圆凸脊
# "inward_fillet" = v48: 方案A+内圆角平滑接缝(只内收+下沉绝不外扩→无M形;
#                   quintic零斜率起步与皮肤切线连续)
SOCKET_VARIANT = "inward_fillet"
SOCKET_RELAX_PASSES = 6      # 松弛迭代次数
SOCKET_RELAX_LAMBDA = 0.5    # 松弛步长

# ---- v62(2026-09-14) 开孔方式: 洪泛删面 → 棱柱 boolean EXACT 切割 ----
# 根因(实测): 洪泛删面的洞边界只能落在网格边环上 → 到手描轮廓偏差最大 ~1mm(网格量化),
#   红材质边界因此有 ~1mm 锯齿/尖角(用户GUI截图所见"红材质溢出到环外三角面"的残余部分).
# boolean: 棱柱侧壁 = 过轮廓段的竖直平面 → 切出边界XZ投影必然落在轮廓折线上.
#   spike实测(_spike_boolexact*): 偏差 中位0.0000mm 均值0.0005 最大0.047mm, 边界222顶点单一闭合环;
#   耗时 7.9s(1.93M面); 旧方案边界84顶点、偏差中位0.09~0.15 最大0.90~1.00mm.
# "floodfill" = 旧路径, 保留作 A/B 对比与回退.
SOCKET_CUT_MODE = "boolean"
PRISM_FRONT_MM = 80.0        # 棱柱前端伸出眼中心的距离(需在脸面之前)
PRISM_BACK_MM = 45.0
# v67: 切割方向跟随局部表面法向(用户诊断: 沿Y垂切遇到"跟前视图近似平行"的面, 交线会跳→环折)
CUT_FOLLOW_NORMAL = False   # 实测否决: 每点扫出方向不同→相邻切割壁互相穿插→boolean出垃圾(L洞口消失/R破环)。见日志 v67
NORMAL_MAX_DEG = 55.0        # 扫出方向与Y轴的最大夹角(防扫出体自交)
         # 棱柱后端伸入颅内距离(需穿过整个眼区)
WALL_TOL_MM = 0.05           # 判定"洞壁面"的容差(所有顶点贴轮廓折线) → 切割后删掉, 留出洞口

# ---- v64: 轮廓光滑化(根源修 rim 环折角) ----
# 根因(实测 _diag_rim3d.py): 手描 72 点轮廓自身 turn mean5.2°/max65.7°(+180°退化尖点),
#   boolean 切出的边界 XZ 投影严格=该轮廓 → 折角 1:1 复制到 rim 环, 换角度看就是"急转弯"。
# 做法: 等弧长重采样 + 闭合DFT低通(只留前 N 次谐波) → 形状不变、折角磨掉。
RIM_CONTOUR_SMOOTH = True
RIM_CONTOUR_RESAMPLE = 240     # 重采样点数(棱柱边数, 越密切出的环越细)
RIM_CONTOUR_HARMONICS = 12     # 保留谐波数(越小越光滑; 12 → 眼角曲率半径≈1mm, 折角14°, 与手描偏差0.33mm)

# ---- v64: rim 环清理(焊接退化小边 + 去刺) ----
RIM_WELD_MM = 0.06             # 环上退化小边焊接阈值(网格边长0.3mm; 过大会把窄颈焊成X自交)
RIM_SPIKE_RELAX_THRESH_DEG = 25  # 环上转角超过此值判为退化尖点, 做环内局部松弛
RIM_SPIKE_RELAX_PASSES = 12
RIM_SPIKE_RELAX_LAMBDA = 0.45
# v64b: 环上尖点处的【局部表面】去噪(实测 L 环 7 个 >30° 顶点全集中在"下睑靠外眼角"一处,
#   该处表面 2mm 内深度起伏 1.5mm → 环贴上去只能跟着折). 只动那一小片, 带位移上限。
RIM_SPIKE_SURF = True
# v64c: rim 环【深度 y 剖面】低通(XZ不动) — 治 L 侧"下睑靠外眼角"那处 1.2mm 表面台阶造成的 30~38° 折角
RIM_DEPTH_SMOOTH = False
# v68: 环重建(等弧长重采样 + 深度按弧长低通) —— 不碰表面/不碰轮廓线, 代价是环略离面
RIM_REBUILD_RING = False
# v70: 去 rim 环的自交折返小尖(实测 L 环 XZ 自交 6 处, 全在下睑外侧那 3mm —— 用户看到的"缺口")
RIM_REMOVE_FOLDS = False
# v73(D): 折返处 rim 边界重建 —— 删折返处围绕 rim 的一小片皮肤, 沿手描轮廓重建内圈并缝合
RIM_PATCH_ENABLE = True
# v85(D2): 沿整圈 rim 重建皮肤带(一次解决折返/锯齿/间距不均)
RIM_BAND_ENABLE = True
RIM_BAND_W_MM = 1.2
RIM_BAND_VERT_CRIT = {"L": True, "R": False}  # R 外眼角是粗面区, 开这条会吃出大洞          # 沿轮廓向外删多宽的皮肤面
RIM_BAND_FLIP_Y = 0.1        # 眼区前表面法线朝后超过此值 → 翻正(与面朝向显示一致)
RIM_BAND_FINE_MM = 0.8       # 带区域内大于此的边先细分(防缝合面被拉长)
RIM_BAND_ARC_MM = 0.5        # 带外缘边长上限(超过就细分)
RIM_BAND_MAX_FACES = 12000    # 单次最多删多少面(安全闸)

RIM_PATCH = {}  # 已改为自动定位折返, 此项留空   # side: (圆心相对眼中心 dx, dz, 圆盘外径mm)
RIM_PATCH_DEPTH_PASSES = 20
RIM_PATCH_CLUSTER_MM = 2.0     # 折返点聚类阈值(同一簇共用一个圆盘)
RIM_PATCH_ARC_MM = 0.5        # 圆盘周界边长于此就细分(保证缝合均匀)
RIM_PATCH_MAX_R_MM = 6.0      # 圆盘半径上限(超过就放弃, 防越修越大)
RIM_PATCH_MAX_FACES = 300     # 单次补片最多删多少面
RIM_PATCH_PAD_MM = 3.0        # 圆盘半径 = 折返跨度 + 该值
RIM_PATCH_DEPTH_CAP_MM = 0.30 # 内圈深度偏离原表面的硬上限
            # 内圈深度弧长低通次数
RIM_PATCH_RAMP = 6                     # 两端几段内把深度修正拉回真实交界点
  # 实测两次都把握不好(切边+焊接 / 删段+焊接 都会把环弄烂) → 先关
   # 先关(它把折返暴露/放大); 折返修好后再评估
RIM_REBUILD_PASSES = 60
RIM_REBUILD_LAMBDA = 0.40
RIM_REBUILD_CAP_MM = 0.60   # 环可离面的最大量(加强低通后) 
RIM_REBUILD_MAX_MM = 0.35      # 长于此的环边对半拆分
RIM_REBUILD_MIN_MM = 0.12      # 短于此的环边合并


# v64d: 轮廓【局部内收】表 —— 绕开"跟前视图近乎平行"的陡面(沿Y垂切会让环的y跳/折角)。
# 格式: [(side, 相对眼中心的 dx_mm, dz_mm, 作用半径mm, 内收量mm)]
RIM_LOCAL_INSET = [
    # ("L", -7.3, -6.3, 4.0, 1.5),  # 实测: 指标好看(转角37.7→28.7°)但正面洞口轮廓被拽进1.5mm, 用户一眼看出"不对" → 停用
]
   # 实测否决: y二阶差分降到0.007mm但3D转角反而恶化(L 5→25个>30°, R 0→26个, 顶点XZ间距不均→索引域低通在弧长上成阶梯)
RIM_DEPTH_PASSES = 8
RIM_DEPTH_LAMBDA = 0.40
RIM_DEPTH_CAP_MM = 0.35

RIM_SPIKE_SURF_R_MM = 3.0      # 以坏点为中心的平滑半径
RIM_SPIKE_SURF_PASSES = 16
RIM_SPIKE_SURF_LAMBDA = 0.12
RIM_SPIKE_SURF_CAP_MM = 0.40   # 允许的表面最大位移(超过即停)

# ---- v64: rim 带局部去噪(实测: 对"折角"无效, 只微降表面噪声; 且表面位移可达1.6mm → 默认关闭) ----
RIM_DENOISE = False
RIM_DENOISE_BAND_MM = 2.5     # 带宽度(mm, 按到轮廓折线的XZ距离)
RIM_DENOISE_PASSES = 12       # 平滑迭代次数
RIM_DENOISE_LAMBDA = 0.5      # 每步强度

# ---- v64: 切割后掏空环内(用户方案: 高模只留 rim 环+空洞, 眼窝在QR低模上补) ----
# True  = 删掉 boolean 切出的坑壁+坑底 → 环内全空, 无需材质分区/UV重映射;
# False = 保留坑(pit)当眼窝(v63路径).
SOCKET_EMPTY_INTERIOR = True

# v48 内圆角参数(平滑脸与眼窝接缝)
SOCKET_FILLET_RINGS = 4        # 内圆角环数
SOCKET_FILLET_INWARD = 0.0012  # 内收量(米)=1.2mm
SOCKET_FILLET_DEPTH = 0.0006   # 圆角下沉深度(米)=0.6mm

# 检测参数 (v2: 全脸眼带+K-means外簇+最暗核心, 不再靠种子点)
EYE_BAND_Z_MIN = 1.60   # 眼带z下限(米)
EYE_BAND_Z_MAX = 1.70   # 眼带z上限
EYE_BAND_Y_MAX = -0.08  # 眼带前侧(y小于此=朝脸前)
EYE_BAND_X_MAX = 0.08   # 眼带|x|上限(避开耳/鼻两侧)
DARK_PCT = 10           # 该侧最暗像素百分位(取瞳孔候选)
PUPIL_CORE_PCT = 30     # 外侧簇里最暗核心百分位(瞳孔比眼睑阴影更暗)

# 旧参数(仅存档, v2不再使用)
BAND_MIN = 0.008
BAND_MAX = 0.020
