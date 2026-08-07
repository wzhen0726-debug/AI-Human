"""01A眼窝与眼球 - 眼窝配置参数

全部尺寸单位: 米(Blender内部单位), 注释给mm。
眼窝位置: 01高模修复之后、02 QR之前。
"""
import os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
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
EYELID_CONTOUR_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour.json")
USE_EYELID_CONTOUR = True   # True=用3DDFA眼睑轮廓开孔(杏仁), False=回退对称椭圆

# 压凹范围与深度
SOCKET_RADIUS = 0.015   # 压凹影响半径 15mm
SOCKET_DEPTH = 0.010    # 最深 10mm
CUP_DEPTH_RATIO = 1.5   # 封碗底深度 = SOCKET_DEPTH * 此值 (15mm, 保证眼球后有封闭背景)

# 平滑半椭圆碗 (make_eye_cup)
CUP_SEGMENTS = 32       # 经线段数(绕碗口, 越大越平滑)
CUP_RINGS = 8           # 纬线圈数(口沿->碗底, 深度方向平滑度)
CUP_DEPTH = 0.020       # 碗最深 20mm (2026-08-06: 12mm不够, 眼球r14.5mm后极需~17mm深, 20mm留余量防穿透)

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
