"""01A眼窝与眼球 - 眼窝配置参数

全部尺寸单位: 米(Blender内部单位), 注释给mm。
眼窝位置: 01高模修复之后、02 QR之前。
"""
import os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
IN_BLEND = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
SHOT_DIR = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots")

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
PRISM_BACK_MM = 45.0         # 棱柱后端伸入颅内距离(需穿过整个眼区)
WALL_TOL_MM = 0.05           # 判定"洞壁面"的容差(所有顶点贴轮廓折线) → 切割后删掉, 留出洞口

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
