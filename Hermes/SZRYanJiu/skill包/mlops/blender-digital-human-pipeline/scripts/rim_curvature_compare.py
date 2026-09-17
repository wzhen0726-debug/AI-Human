# rim 曲率质量对比: 两侧环的转角剖面 + 腔体着色对比渲染
# 用途: 用户说"某侧 rim 不圆 / 有多个凸起 / 对比另一侧"时, 先跑这个定性与定量同时到位。
# 用法: EYE_OUT_BLEND=<blend> EYE_CONTOUR_JSON=<手描 json> [EYE_SHOT_DIR=<输出目录>] \
#         blender -b --factory-startup --python scripts/rim_curvature_compare.py
# 判读:
#   ① 转角剖面按侧对比(mean/max/>28° 点数): 尖锐点多的那侧才是问题侧;
#   ② 渲出的 rim_L/R_{front,a25,a45}.png 交给 vision 做"同设置对侧对比", 不要单张绝对描述;
#   ③ 不要用"相对平滑副本的最大偏移"当主判据(高曲率处基线自缩 ~0.77mm, 会造假突刺)。
import bpy, os, json, math
import numpy as np, bmesh
from mathutils import Vector

F = os.environ.get("EYE_OUT_BLEND"); J = os.environ.get("EYE_CONTOUR_JSON")
assert F and J, "需要 EYE_OUT_BLEND 与 EYE_CONTOUR_JSON"
Jd = json.load(open(J, encoding="utf-8"))
SHOT = os.environ.get("EYE_SHOT_DIR") or os.path.join(os.path.dirname(F), "screenshots")
os.makedirs(SHOT, exist_ok=True)
print("输入:", os.path.basename(F), "| 轮廓:", os.path.basename(J))
bpy.ops.wm.open_mainfile(filepath=F)
head = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
bm = bmesh.new(); bm.from_mesh(head.data)
bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.normal_update()


def walk_ring(c):
    oe = [e for e in bm.edges if len(e.link_faces) == 1
          and (e.verts[0].co - c).xz.length < 0.05 and e.verts[0].co.y < c.y + 0.02]
    deg = {}
    for e in oe:
        a, b = e.verts[0].index, e.verts[1].index
        deg.setdefault(a, []).append(b)
        deg.setdefault(b, []).append(a)
    n_end = sum(1 for k in deg if len(deg[k]) != 2)
    st = [k for k in deg if len(deg[k]) == 2]
    if not st:
        return [], n_end
    ring = [st[0]]; prev, cur = -1, st[0]
    while True:
        nxt = [n for n in deg[cur] if n != prev]
        if not nxt or nxt[0] == ring[0] or len(ring) > 200000:
            break
        ring.append(nxt[0]); prev, cur = cur, nxt[0]
    return ring, n_end


vm = {v.index: v for v in bm.verts}
for side in ("L", "R"):
    if side not in Jd:
        continue
    c = Vector(tuple(float(x) for x in Jd[side]["center"]))
    ring, n_end = walk_ring(c)
    if len(ring) < 10:
        print(f"{side}: 环追踪失败(非2度端点 {n_end})")
        continue
    P = np.array([vm[k].co[:] for k in ring]); n = len(P)
    d = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    spt = np.concatenate([[0], np.cumsum(d)[:-1]])
    turn = np.zeros(n)
    for i in range(n):
        v1 = P[i] - P[(i - 1) % n]; v2 = P[(i + 1) % n] - P[i]
        n1 = np.linalg.norm(v1); n2 = np.linalg.norm(v2)
        if n1 > 1e-12 and n2 > 1e-12:
            turn[i] = np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1)))
    print(f"{side}: 环{len(ring)}顶点 非2度端点{n_end} 周长{d.sum()*1000:.1f}mm | "
          f"转角 mean{turn.mean():.1f} max{turn.max():.1f} >28° {int((turn > 28).sum())} 个")
    for i in [i for i in range(n) if turn[i] > 28][:6]:
        print(f"    尖锐点 弧长{spt[i]*1000:.1f}mm 转角{turn[i]:.0f}° "
              f"xz=({P[i,0]*1000:.1f},{P[i,2]*1000:.1f}) y={P[i,1]*1000:.1f}")

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
sh = scn.display.shading
sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.75, 0.75, 0.77)
sh.show_cavity = True; sh.cavity_type = 'BOTH'
scn.render.resolution_x, scn.render.resolution_y = 1400, 1100
cam = bpy.data.objects.new("_rimcam", bpy.data.cameras.new("_rimcam"))
scn.collection.objects.link(cam); scn.camera = cam; cam.data.type = 'ORTHO'
for side in ("L", "R"):
    if side not in Jd:
        continue
    c = Vector(tuple(float(x) for x in Jd[side]["center"]))
    for ang, nm in ((0, "front"), (25, "a25"), (45, "a45")):
        a = math.radians(ang)
        cam.location = c + Vector((0.6 * math.sin(a), -0.6 * math.cos(a), 0.01))
        cam.rotation_euler = (1.5707963, 0, a)
        cam.data.ortho_scale = 0.042
        scn.render.filepath = os.path.join(SHOT, f"rim_{side}_{nm}.png")
        bpy.ops.render.render(write_still=True)
print("渲图完成 ->", SHOT)
bm.free()
