"""修正版验证: 正确测碗底深度(碗在开口平面后方=更大y, 取区域内max y) + rim带偏差.
上一版bug: 碗深误用了区域内min y(最前点=鼻尖), 本版改正."""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HIGH_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
CONTOUR_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")


def point_in_poly(x, z, poly):
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, zi = poly[i]; xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside


def main():
    cont = json.load(open(CONTOUR_JSON, encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=HIGH_BLEND)
    hi = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    mat = hi.matrix_world
    hi_pts = np.array([(mat @ v.co)[:] for v in hi.data.vertices])
    hi_bvh = BVHTree.FromObject(hi, bpy.context.evaluated_depsgraph_get())
    bpy.ops.wm.append(filepath=os.path.join(LOW_BLEND, "Object", "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"),
                      directory=os.path.join(LOW_BLEND, "Object"), filename="tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
    lo = bpy.data.objects["tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"]
    mat = lo.matrix_world
    lo_pts = np.array([(mat @ v.co)[:] for v in lo.data.vertices])

    for side in ("L", "R"):
        rim = np.array(cont[side]["rim_3d"])
        c = np.array(cont[side]["center"])
        rim_y = float(rim[:, 1].mean())
        poly = [(p[0], p[2]) for p in rim]

        # 高模/低模 碗底深度(碗内最大y = 最后方点, 相对开口平面, 正值=在平面后方)
        hi_in = np.array([p for p in hi_pts if point_in_poly(p[0], p[2], poly)])
        lo_in = np.array([p for p in lo_pts if point_in_poly(p[0], p[2], poly)])
        hi_bottom = hi_in[:, 1].max()
        lo_bottom = lo_in[:, 1].max()
        hi_depth = (hi_bottom - rim_y) * 1000
        lo_depth = (lo_bottom - rim_y) * 1000
        print(f"{side}: 碗底深度(开口平面后方) 高模={hi_depth:.1f}mm 低模={lo_depth:.1f}mm 保持率={lo_depth/hi_depth*100:.0f}%")

        # rim带(开口边缘±3mm深度)低模点偏差 — 眼睑外观关键区
        lo_in2 = lo_pts[[point_in_poly(p[0], p[2], poly) for p in lo_pts]]
        depth_arr = (lo_in2[:, 1] - rim_y) * 1000  # 正=后方
        rim_band = lo_in2[np.abs(depth_arr) < 3.0]
        dists = []
        for p in rim_band:
            loc, *_ = hi_bvh.find_nearest(Vector(p))
            if loc:
                dists.append((Vector(p) - loc).length)
        dists = np.array(dists) * 1000
        print(f"{side}: rim带(±3mm) 低模顶点={len(rim_band)} 偏差 均值={dists.mean():.3f} 中位={np.median(dists):.3f} P95={np.percentile(dists,95):.3f} 最大={dists.max():.3f}mm")
    print("FIX_VERIFY_DONE")


if __name__ == "__main__":
    main()
