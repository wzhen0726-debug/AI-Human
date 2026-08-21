"""按用户审美标准算眼珠位置并渲染对比:
标准: 上眼皮盖住虹膜顶部约25%, 下眼皮贴住虹膜下缘(完整露出).
步骤: 1)在已摆好的Eye002_L上, 从角膜顶点BFS找虹膜镜片区域, 测外圈直径(纯几何, 不依赖材质名)
      2)按开口上下缘+虹膜直径算3组候选高度; 深度统一把角膜顶点收到眼睑缘平面后1.5mm(解决凸出)
      3)逐组渲染正面+特写, 供用户挑选"""
import bpy, os, sys, json
from collections import deque
import numpy as np
from mathutils import Vector
import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye002_config import *
import run_eyeball_v2 as rev2

DEPTH_MM = -1.5   # 角膜顶点收到眼睑开口平面后方1.5mm(负=靠里, 解决"凸出")


def measure_iris_diameter(eye):
    """纯几何: 角膜最前顶点出发BFS找虹膜镜片面片, 取外圈最大半径."""
    bm = bmesh.new()
    bm.from_mesh(eye.data)
    bm.transform(eye.matrix_world)
    bm.verts.ensure_lookup_table()
    # 角膜顶点 = y最小的顶点(脸朝-Y)
    apex = min(bm.verts, key=lambda v: v.co.y)
    start_face = apex.link_faces[0]
    # BFS 收集连通面片(虹膜镜片是独立壳, 不会漏到巩膜)
    seen = {start_face.index}
    q = deque([start_face])
    patch = []
    while q:
        f = q.popleft()
        patch.append(f)
        for e in f.edges:
            for nf in e.link_faces:
                if nf.index not in seen:
                    seen.add(nf.index)
                    q.append(nf)
    pts = np.array(list({v.index: v.co for f in patch for v in f.verts}.values()))
    pts = np.array([v.co[:] for f in patch for v in f.verts])
    cen = pts.mean(axis=0)
    rad = np.sqrt((pts[:, 0] - cen[0])**2 + (pts[:, 2] - cen[2])**2)
    d = 2.0 * float(np.percentile(rad, 99))   # 外圈直径(取99分位抗毛刺)
    print(f"IRIS: 面片数={len(patch)} 直径={d*1000:.2f}mm 镜片中心z={cen[2]:.4f}")
    bm.free()
    return d


def render_shots(tag):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    eyes = [o for o in bpy.data.objects if o.name.startswith("Eye002")]
    fc = sum((o.location for o in eyes), Vector((0, 0, 0))) / 2
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 85
    for name, pos in [("front", Vector((fc.x, fc.y - 0.30, fc.z))),
                      ("close", Vector((fc.x, fc.y - 0.12, fc.z)))]:
        cam.location = pos
        cam.rotation_euler = (fc - pos).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"tune2_{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    cont = json.load(open(EYE_XZ_JSON, encoding="utf-8"))
    eyes = {o.name: o for o in bpy.data.objects if o.name.startswith("Eye002")}
    D = measure_iris_diameter(eyes["Eye002_L"])
    print(f"IRIS_FINAL: 虹膜直径={D*1000:.1f}mm")

    data = {}
    for side in ("L", "R"):
        pts = np.array(cont[side]["rim_3d"])
        c = np.array(cont[side]["center"])
        z_top, z_bot = float(pts[:, 2].max()), float(pts[:, 2].min())
        rim_y = float(pts[:, 1].mean())
        corneal = rev2.measure_corneal_dist(eyes[f"Eye002_{side}"])
        eye_y = rim_y + corneal - DEPTH_MM / 1000.0
        z_bottom = z_bot + D / 2          # P1: 下睑贴虹膜底
        z_cover = z_top - 0.25 * D        # P3: 上睑盖虹膜25%
        z_mid = (z_bottom + z_cover) / 2  # P2: 折中
        print(f"{side}: 上缘z={z_top:.4f} 下缘z={z_bot:.4f} 开口高={(z_top-z_bot)*1000:.1f}mm 角膜距={corneal*1000:.2f}mm")
        print(f"{side}: P1下贴底z_off={(z_bottom-c[2])*1000:+.2f} P2折中z_off={(z_mid-c[2])*1000:+.2f} P3上盖25%z_off={(z_cover-c[2])*1000:+.2f} 球心y={eye_y:.4f}(角膜在睑缘后{-DEPTH_MM:.1f}mm)")
        data[side] = (c, eye_y, z_bottom, z_mid, z_cover)

    for tag, idx in [("P1_下睑贴虹膜底", 2), ("P2_折中", 3), ("P3_上睑盖25", 4)]:
        for side in ("L", "R"):
            c, eye_y, z_bottom, z_mid, z_cover = data[side]
            eyes[f"Eye002_{side}"].location = (c[0], eye_y, (z_bottom, z_mid, z_cover)[idx - 2])
        render_shots(tag)
    print("done — blend未保存, 挑选后写入eye002_config重跑")


if __name__ == "__main__":
    main()
