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

# 虹膜中心 (从01_1检测)
IRIS_L = (-0.0225, -0.1061, 1.6660)
IRIS_R = (0.0215, -0.1076, 1.6632)

# 开口中心 (实测, 比虹膜中心更靠外)
OPENING_L = (-0.0275, -0.1097, 1.6654)
OPENING_R = (0.0248, -0.1106, 1.6644)

# 眼球摆入参数
EYE_SCALE = 1.0          # 眼球缩放 (先1.0, 渲染定夺)
EYE_PUSH_IN = 0.022      # 沿-Y内缩22mm (球心位置, 角膜探出约2mm)
PUPIL_LOCAL_DIR = (0, -0.04, 0.997)  # 瞳孔在局部+Z轴
