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

# 虹膜中心 (v2算法: 全脸眼带+K-means外簇+最暗30%核心, 作为眼球x/z基准)
# 2026-08-06: 旧算法偏鼻梁(眼间距测小42%), v2实测间距71.7mm与vision标定一致
IRIS_L = (-0.0369, -0.1121, 1.6762)
IRIS_R = (0.0348, -0.1126, 1.6761)

# 3DDFA反投影结果 (精确定位眼部, 替代暗像素法; x/z=角膜表面交点=眼球中心基准)
DDFA_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "iris_3ddfa.json")
USE_3DDFA = True   # True=用3DDFA语义定位, False=回退暗像素法IRIS_L/IRIS_R

# 眼窝唇缘前缘y (环前缘实测, 用于计算眼球深度)
# 注: 3DDFA模式下眼窝已按新中心重建, run_eyeball会自动从blend实测唇缘, 此值为回退默认
RIM_FRONT_Y_L = -0.1256
RIM_FRONT_Y_R = -0.1251

# 眼球摆入参数 (几何定参)
EYE_SCALE = 1.0            # 眼球缩放
EYE_RADIUS = 0.0145        # 眼球半径 14.5mm (直径29mm实测)
# 2026-08-06终版: 球心=拟合虚拟原始眼球球心. 
# 原始高模眼睛是画出来的鼓包, 球面拟合得虚拟眼球球心y=-0.1202(L)/-0.1206(R), r=16.6mm.
# 角膜前极=球心y-14.5mm=-0.1347, 与原始眼睑apex(-0.129)接近 -> 眼球位置与原始鼓包一致, 不错.
# 经历: 3DDFA角膜点(-0.1058,太前)->唇缘反推->apex对齐(-0.1145)->上睑缘(-0.1027/-0.1097,都是洞缘被压凹后的位置,仍太前).
# 侧视图证实: 必须回到拟合球心, 角膜前极对齐原始眼睑最凸点.
# x/z=3DDFA(准), y=拟合球心y.
CORNEA_PROTRUDE = -0.0005  # (弃用)
EYE_PUSH_BACK = 0.022      # +Y=头内=后移. 2026-08-07用户: 眼球还是突出,下眼皮被盖住,再往里推. 0.020->0.022
EYE_WIDEN = 0.0            # 眼间距加宽(默认0, 眼球跟虹膜走, 不强行加宽)
# 球心: x/z=虹膜质心, y=唇缘前缘+半径-探出量+PUSH_BACK
# 瞳孔朝向: 实测GLB瞳孔在局部-Y(下方), 需转到全局-Y(正前方)
PUPIL_LOCAL_DIR = (0, -1.0, 0.0)  # 瞳孔在局部-Y轴 (GUI实测瞳孔朝下)
