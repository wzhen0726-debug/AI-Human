"""01A眼窝与眼球 - 眼球摆入配置

位置: 01高模修复之后、02 QR之前。
眼球独立物体, 不进QR, 只在05绑定、06导出时并入。
"""
import os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
SHOT_DIR = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots")

# 眼球GLB路径
EYE_GLB = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型001\eye_01.glb"

# 虹膜中心 (01A 本次检测)
IRIS_L = (-0.0225, -0.1061, 1.6660)
IRIS_R = (0.0215, -0.1076, 1.6632)

# 眼窝开口几何中心 (实测: 开口边界环 x/z 均值, 来自01_1 blend边界环测量)
OPENING_L = (-0.0270, -0.1182, 1.6681)   # y=洞口唇缘前缘
OPENING_R = (0.0193, -0.1216, 1.6629)

# 眼球摆入参数 (几何定参, 不再盲调)
EYE_SCALE = 1.0            # 眼球缩放 (先1.0, 渲染定夺)
EYE_RADIUS = 0.0145        # 眼球半径 14.5mm (直径29mm实测)
CORNEA_PROTRUDE = 0.004    # 角膜探出唇缘量 4mm (标准3-5mm取中值)
# 球心 y = 唇缘前缘y - (半径 - 探出量), 在 run_eyeball 里按此计算
PUPIL_LOCAL_DIR = (0, -0.04, 0.997)  # 瞳孔在局部+Z轴
