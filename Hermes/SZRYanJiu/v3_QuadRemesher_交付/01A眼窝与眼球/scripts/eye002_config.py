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

# ---- v4 摆位定案: 解剖规律(用户GUI手动微调反推, 2026-08-21验收) ----
# 深度参考 = 眼睑开口平面(用户标记的rim, 左右几乎完全对称 → 两眼深度自动同步)
# 眼珠中心y = 开口平面y + (角膜顶点距 - 凸出量)
#
# 【规律1·深度】角膜顶点与睑缘开口平面共面(凸出≈0).
#   用户手动把v3e的-1.5mm往前拉1.57mm回到共面位 → 定案0.1mm
#   眼球太凸 → 减小此值(更靠里); 眼球凹陷 → 增大此值
EYE_PROTRUSION_MM = 0.1
#
# 【规律2·高度】虹膜底缘贴下眼睑缘(可见虹膜, limbus透明区约0.5mm已含在内).
#   等效: 虹膜中心 = 开口中心 +1.4mm(002实测); 上睑自然盖住虹膜顶约1.5mm
#   换模型时若虹膜尺寸不同, 半自动微调面板可GUI调整后"保存到管线"
EYE_Z_OFFSET_MM = 1.4
#
# 【规律3·左右】x=轮廓中心不动; 两眼y/z用同一偏移量 → 天然同步
# 【半自动微调】GUI手动调好后点面板"保存位置到管线" → 写入 eyeball_finetune_manual.json,
#   本脚本重跑时自动加载该文件覆盖上面两个旋钮(优先用户验收值)
#
# (旧参数 EYE002_PUSH_BACK/EYE002_Z_OFFSET 已废弃, 由上面两个毫米旋钮替代)

# ---- 眼睛颜色选项 (19变体) ----
# 色系: Blue / Brown / Green / Hazel / Red / Violet / Zombie
# 血丝: base(无) / Bld1(中) / Bld2(重); Zombie只有base
EYE_COLOR = "Hazel"
EYE_BLOODLINE = "base"
