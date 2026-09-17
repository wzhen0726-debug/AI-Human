# -*- coding: utf-8 -*-
"""眼窝几何一次性复核(只读, 不保存任何 blend): 碗深 / 眼球包围 / 回退检查 + 侧视tag上色渲染.

跑法(改上面 D 指向工程根):
    blender -b --factory-startup --python verify_eye_socket_geometry.py

判据(全部实测口径):
    碗深         = 眼中心柱内 tag 碗面(且 y<0) 最深 y − 手描开口平面 y
    包住眼球     = 碗最深 y − 眼球后极 y > 0        (球后极取 bbox max y)
    真凹进脸里   = 碗最深 y − 脸面基准(同高度太阳穴/脸颊) > 0
    无回退       = 开放边/非流形边与旧版一致; 眉毛区(z>1680 且 |dx|<25mm)面数不变

三个坑(都真踩过, 直接决定结论对错):
    1) 眼中心柱必须加 y<0 —— 不加会抓到颅后壁(y≈+94mm), 算出「碗深 +200mm」的荒谬值;
       y 符号约定: 越负越靠前(脸外), 越大越深(颅内).
    2) 眼球中心用 bbox 中心, **不要用顶点质心** —— 质心被角膜侧密集顶点拉偏约 4mm;
       角膜顶点距要取 run_eyeball_v2 运行时实测值(本 asset 15.31mm), 不要用质心反推(得 11.2mm).
    3) 渲染上色按 v44tag 层, **不要按材质槽名** —— 装配态 01_2 没有 EyeSocket 槽,
       按名涂红会把碗面涂成皮肤色 → 假通过(「零红像素」) → 掩盖眼角露碗等真缺陷.
"""
import os
import json

import bpy
import bmesh
import numpy as np
from mathutils import Vector

# ── 工程根(改这里即可迁移) ────────────────────────────────────────────
D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
DELIV = os.path.join(D, "交付", "01A眼窝与眼球")
M = os.path.join(DELIV, "models")
LOGS = os.path.join(D, "logs")
BM = os.path.join(D, "02QR拓扑", "输出", "02QR输入_眼窝材质分区_高模.blend")
BOWL_BLEND = os.path.join(M, "01_1_eye_socket.blend")          # 空窝态(带 tag 层)
ASM_BLEND = os.path.join(M, "01_2_eyeball_placed.blend")       # 装配态(带眼球)
FACE_BASE_MM = -82.0   # 脸面基准: 同高度太阳穴/脸颊的 y(mm)

EYE = {}
try:
    _d = json.load(open(os.path.join(DELIV, "screenshots", "3ddfa", "iris_3ddfa.json"), encoding="utf-8"))
    EYE = {k: np.array(_d[k]["center_3d"], dtype=float) for k in ("L", "R") if "center_3d" in _d.get(k, {})}
except Exception as _e:
    print(f"!! iris_3ddfa.json 读失败: {_e}")
_cont = json.load(open(os.path.join(DELIV, "screenshots", "3ddfa", "eyelid_contour_manual.json"), encoding="utf-8"))


def head_and_balls(objs):
    """最大 mesh = 头, 其余 = 眼球"""
    head = max(objs, key=lambda o: len(o.data.vertices))
    return head, [o for o in objs if o is not head]


def verify():
    print("=" * 70)
    print(f"装配态: {ASM_BLEND}")
    bpy.ops.wm.open_mainfile(filepath=ASM_BLEND)
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    head, balls = head_and_balls(objs)
    ball_y = {}
    for o in balls:
        V = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) * 1000
        s = "L" if V[:, 0].mean() < 0 else "R"
        ball_y[s] = (V[:, 1].min(), V[:, 1].max())
        print(f"  眼球 {o.name}: y前极 {V[:,1].min():+.2f}  后极 {V[:,1].max():+.2f}  "
              f"bbox中心 {(V[:,1].min()+V[:,1].max())/2:+.2f}  (别用质心 {V[:,1].mean():+.2f})")

    mw = head.matrix_world
    bm = bmesh.new()
    bm.from_mesh(head.data)
    bm.faces.ensure_lookup_table()
    tL = bm.faces.layers.int.get("v44tag_L")
    tR = bm.faces.layers.int.get("v44tag_R")
    FC = np.array([(mw @ f.calc_center_median())[:] for f in bm.faces]) * 1000
    TAG = {s: np.array([f[ly] if ly else 0 for f in bm.faces]) for s, ly in (("L", tL), ("R", tR))}
    n_open = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    n_non = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    for s, c in EYE.items():
        cc = c * 1000
        bowl = TAG[s] == 2
        sel = bowl & (FC[:, 1] < 0)                       # 坑1: 必须 y<0
        d_xz = np.sqrt((FC[:, 0] - cc[0]) ** 2 + (FC[:, 2] - cc[2]) ** 2)
        col = sel & (d_xz < 3)
        deepest = (FC[col][:, 1].max() if col.sum() else FC[sel][:, 1].max())
        rimp = _cont[s]["center"][1] * 1000
        rear = ball_y.get(s, (0, 0))[1]
        brow = int(((np.abs(FC[:, 0] - cc[0]) < 25) & (FC[:, 2] > 1680)).sum())
        print(f"  {s}: tag碗面 {int(bowl.sum())}  最深 {deepest:+.2f}mm  碗深 {deepest - rimp:+.2f}mm  "
              f"碗底-球后极 {deepest - rear:+.2f}mm {'✓包住' if deepest > rear else '✗戳穿'}  "
              f"碗底-脸面基准 {deepest - FACE_BASE_MM:+.2f}mm "
              f"{'✓真凹进脸里' if deepest > FACE_BASE_MM else '✗仍是浅碟'}  眉毛区面数 {brow}")
    print(f"  开放边 {n_open}  非流形边 {n_non}  (与旧版对比, 变了就是回退)")
    bm.free()


def render_by_tag(src=BOWL_BLEND, out_prefix="bowlcheck"):
    """按 v44tag 上色渲染: 侧视正交(看凹凸) + 前视特写(看边界/形状)"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=src)
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.display.shading.light = 'STUDIO'
    scn.display.shading.color_type = 'MATERIAL'
    scn.display.shading.show_cavity = False
    scn.world.color = (0.06, 0.06, 0.08)
    scn.render.resolution_x, scn.render.resolution_y = 1100, 900
    head, _ = head_and_balls([o for o in bpy.data.objects if o.type == 'MESH'])
    me = head.data
    red = bpy.data.materials.get("BowlRed") or bpy.data.materials.new("BowlRed")
    red.use_nodes = True
    red.diffuse_color = (0.85, 0.10, 0.10, 1.0)
    if red.name not in [m.name for m in me.materials if m]:
        me.materials.append(red)
    ri = [m.name for m in me.materials if m].index(red.name)
    if me.materials[0]:
        me.materials[0].use_nodes = True
        me.materials[0].diffuse_color = (0.58, 0.56, 0.54, 1.0)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    tL = bm.faces.layers.int.get("v44tag_L")
    tR = bm.faces.layers.int.get("v44tag_R")
    idx = np.array([ri if ((tL and f[tL] == 2) or (tR and f[tR] == 2)) else 0 for f in bm.faces], dtype=np.int32)
    bm.free()
    me.polygons.foreach_set("material_index", idx)
    me.update()
    print(f"  按 tag 上色: 碗面 {int((idx == ri).sum())} 个 (绝不按材质槽名上色)")

    L = EYE["L"]
    cd = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cd)
    scn.collection.objects.link(cam)
    scn.camera = cam
    tgt = Vector((L[0], L[1], L[2]))
    for tag, loc, ortho in (("前视", (L[0], L[1] - 0.10, L[2] + 0.004), None),
                            ("侧视", (L[0] - 0.30, L[1], L[2]), 0.075),
                            ("斜侧", (L[0] - 0.16, L[1] - 0.20, L[2] + 0.045), None)):
        if ortho:
            cd.type = 'ORTHO'
            cd.ortho_scale = ortho
        else:
            cd.type = 'PERSP'
            cd.lens = 100
        cam.location = loc
        cam.rotation_euler = (tgt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        scn.render.filepath = os.path.join(LOGS, f"{out_prefix}_{tag}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  {out_prefix}_{tag}.png")


if __name__ == "__main__":
    verify()
    if os.path.exists(BOWL_BLEND):
        render_by_tag(BOWL_BLEND, "bowlcheck")
    print("VERIFY_EYE_SOCKET_DONE")
