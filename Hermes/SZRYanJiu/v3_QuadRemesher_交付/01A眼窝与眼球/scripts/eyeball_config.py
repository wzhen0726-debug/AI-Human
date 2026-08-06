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
# 2026-08-06 GUI反馈: 眼间距偏窄, 眼球位置不对. 眼洞中心沿X外移+WIDEN, 沿Z上移.
OPENING_L = (-0.0270, -0.1182, 1.6681)   # y=洞口唇缘前缘
OPENING_R = (0.0193, -0.1216, 1.6629)

# 眼球摆入参数 (几何定参)
EYE_SCALE = 1.0            # 眼球缩放 (先1.0, 渲染定夺)
EYE_RADIUS = 0.0145        # 眼球半径 14.5mm (直径29mm实测)
CORNEA_PROTRUDE = 0.004    # 角膜探出唇缘量 4mm
EYE_PUSH_BACK = 0.004      # 2026-08-06: 眼球未完全进窝, 额外往头内(+Y)再推4mm
EYE_WIDEN = 0.004          # 2026-08-06: 眼间距偏窄, 左右各沿X外移4mm
# 球心 y = 唇缘y + 半径 - 探出量 + EYE_PUSH_BACK (+Y往头内退)
# 瞳孔朝向: 实测GLB瞳孔在局部-Y(下方), 需转到全局-Y(正前方)
PUPIL_LOCAL_DIR = (0, -1.0, 0.0)  # 瞳孔在局部-Y轴 (GUI实测瞳孔朝下)
