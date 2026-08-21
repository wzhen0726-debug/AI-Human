"""眼睛模型002配置 — 01_2眼球摆入v2用"""
import os

MODEL_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002"
EYE002_BLEND = os.path.join(MODEL_DIR, "Eye.blend")
EYE002_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye002_colors.json")

# Eye.blend内要append的对象(虹膜+巩膜+阴影片)
EYE002_OBJECTS = ["Eye_Iris", "Eye_Sclera", "Eye_Shadow"]

# 眼珠x/z基准: 手动标记轮廓中心(与眼窝同基准, 不再用3DDFA center_3d)
EYE_XZ_JSON = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour_manual.json"

# 缩放: 巩膜实测中位半径12.45mm → 缩到14.5mm(与001方案角膜位置对齐, 保持已验证摆入参数)
EYE002_SCALE = 14.5 / 12.45   # ≈1.1647

# ---- v3 摆位逻辑: 解剖参考点定位 (换模型自动适配) ----
# 深度参考 = 眼睑开口平面(用户标记的rim, 左右几乎完全对称 → 两眼深度自动同步)
# 眼珠中心y = 开口平面y + (角膜顶点距 - 凸出量)
#
# 凸出量(毫米): 角膜顶点凸出眼睑开口平面的量. 直观含义:
#   眼球太凸 → 减小此值(更靠里); 眼球凹陷 → 增大此值
#   定案(v3c): -1.5 = 角膜顶点收到睑缘平面后方1.5mm(用户验收"不凸出")
EYE_PROTRUSION_MM = -1.5
#
# 高度偏移(毫米): 虹膜中心相对眼开口几何中心的垂直偏移(正=上抬).
#   几何解(v3d): 虹膜盘13.2mm > 开口12.2mm → 虹膜底贴下睑需中心+0.5mm
#   但渲染验证(vision): +0.5时虹膜下方仍露一条眼白(可见虹膜<网格盘, 边缘limbus透明)
#   → v3e: 下移0.8mm取-0.3, 上睑覆盖随之略增(符合"上眼皮包裹"审美)
EYE_Z_OFFSET_MM = -0.3
#
# (旧参数 EYE002_PUSH_BACK/EYE002_Z_OFFSET 已废弃, 由上面两个毫米旋钮替代)

# ---- 眼睛颜色选项 (19变体) ----
# 色系: Blue / Brown / Green / Hazel / Red / Violet / Zombie
# 血丝: base(无) / Bld1(中) / Bld2(重); Zombie只有base
EYE_COLOR = "Hazel"
EYE_BLOODLINE = "base"
