"""ARP用户的Mixamo绑定 v2 (2026-08-27): 以用户17点为真源.
原理: 直接打开用户点位文件(07_arp_markers.blend), 在其上生成52骨mixamorig骨架
      (同手写版方案A管线: 朝向照抄Mixamo实测, 位置=用户点), 然后清理模板残留
      (删除标记球/说明牌/cs_*垃圾, 但保留身体mesh), 绑权重, 输出06_rig_arp.blend."""
import bpy, os, sys

# 复用手写版方案A的骨架构建模块(已验证: 静止姿态0偏差/行走通过)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
USERS_PTS = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "07_arp_markers.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "B_骨骼绑定", "06_rig_arp.blend")
SPEC = os.path.join(BASE, "_工作区_过程文件", "logs", "mixamo_rest_spec.json")

# ===== 1) 打开用户点位场景 =====
bpy.ops.wm.open_mainfile(filepath=USERS_PTS)
scn = bpy.context.scene
print(f"USER PTS loaded: objects={len(bpy.data.objects)}")

body = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
assert body, "找不到身体mesh"

# 收集用户标记点 (ARP命名: NN_中文[=对侧镜像])
import json, re
user = {}   # arp_name -> location
mirror_map = {}
for o in scn.objects:
    m = re.match(r"^(\d+)_(.+?)(_对侧镜像)?$", o.name)
    if not m:
        continue
    idx, cn, mir = int(m.group(1)), m.group(2), bool(m.group(3))
    loc = o.location.copy()
    if o.parent:
        loc = o.matrix_world.translation.copy()
    if mir:
        mirror_map[idx] = loc
    else:
        user[idx] = loc

print(f"主点{len(user)}个, 镜像点{len(mirror_map)}个")

# ===== 2) 映射到方案A管线的标准8点输入 =====
def g(idx):
    return user.get(idx) or mirror_map.get(idx)

P = {
    "crotch":   tuple(user[1]),     # 01骨盆中心
    "chin":     tuple(user[2]),     # 02下巴
    "neck":     tuple(user[3]),     # 03颈根
    "shoulder": tuple(g(4)),        # 04肩(+X主)
    "elbow":    tuple(g(5)),
    "wrist":    tuple(g(6)),
    "fingertip":tuple(g(7)),
    "thigh_top":tuple(g(8)),        # 08大腿根上段
    "knee":     tuple(g(9)),
    "ankle":    tuple(g(10)),
}
for k, v in P.items():
    if v is None:
        raise RuntimeError(f"缺用户点 {k}")
print("MAPPED OK")

with open(os.path.join(os.path.dirname(OUT), "arp_user_points.json"), "w", encoding="utf-8") as f:
    json.dump(P, f, ensure_ascii=False, indent=1)
print("STAGE1_DONE")
