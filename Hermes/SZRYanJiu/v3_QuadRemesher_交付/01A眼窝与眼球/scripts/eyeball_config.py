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

# 虹膜中心 (鲁棒质心, 剔除z向离群噪点后实测, 作为眼球x/z基准)
# 2026-08-06: 虹膜质心=真实瞳孔位置, 比删面后的离散环中心更准
IRIS_L = (-0.0228, -0.1058, 1.6662)
IRIS_R = (0.0216, -0.1073, 1.6642)

# 眼窝唇缘前缘y (环前缘实测, 用于计算眼球深度)
RIM_FRONT_Y_L = -0.1172
RIM_FRONT_Y_R = -0.1203

# 眼球摆入参数 (几何定参)
EYE_SCALE = 1.0            # 眼球缩放
EYE_RADIUS = 0.0145        # 眼球半径 14.5mm (直径29mm实测)
CORNEA_PROTRUDE = 0.004    # 角膜探出唇缘量 4mm
EYE_PUSH_BACK = 0.0        # 额外内推(默认0, GUI反馈后调)
EYE_WIDEN = 0.0            # 眼间距加宽(默认0, 眼球跟虹膜走, 不强行加宽)
# 球心: x/z=虹膜质心, y=唇缘前缘+半径-探出量+PUSH_BACK
# 瞳孔朝向: 实测GLB瞳孔在局部-Y(下方), 需转到全局-Y(正前方)
PUPIL_LOCAL_DIR = (0, -1.0, 0.0)  # 瞳孔在局部-Y轴 (GUI实测瞳孔朝下)
