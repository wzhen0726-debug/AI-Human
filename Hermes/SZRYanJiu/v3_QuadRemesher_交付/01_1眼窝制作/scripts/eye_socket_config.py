"""01_1眼窝制作 - 配置参数

全部尺寸单位: 米(Blender内部单位), 注释给mm。
眼窝位置: 01高模修复之后、02 QR之前。
"""
import os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
OUT_BLEND = os.path.join(DELIVERY, "01_1眼窝制作", "models", "01_1_eye_socket.blend")
SHOT_DIR = os.path.join(DELIVERY, "01_1眼窝制作", "screenshots")

# 虹膜中心 (实测, 脚本会重新自动检测校正)
IRIS_L = (-0.0241, -0.1163, 1.6517)
IRIS_R = (0.0229, -0.1168, 1.6507)

# 开孔椭圆尺寸 (半径): 宽26mm/2=13mm, 高18mm/2=9mm
HOLE_RX = 0.013   # 半宽 (内外眼角方向)
HOLE_RZ = 0.009   # 半高 (上下眼睑方向)

# 压凹范围与深度
SOCKET_RADIUS = 0.015   # 压凹影响半径 15mm
SOCKET_DEPTH = 0.010    # 最深 10mm

# 检测参数
BAND_MIN = 0.008   # 眼带内半径
BAND_MAX = 0.020   # 眼带外半径
DARK_PCT = 8       # 贴图暗像素百分位 (8%保证足够样本)
