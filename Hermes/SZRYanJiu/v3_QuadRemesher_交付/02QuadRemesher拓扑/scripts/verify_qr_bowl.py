"""聚焦验证: 只测低模在【眼窝碗内】(rim多边形投影内)的偏差, 排除周围皮肤干扰."""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HIGH_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
CONTOUR_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")


def point_in_poly(x, z, poly):
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
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
        poly = [(p[0], p[2]) for p in rim]
        # 低模碗内顶点: xz投影在rim多边形内
        inside = np.array([point_in_poly(p[0], p[2], poly) for p in lo_pts])
        bowl_pts = lo_pts[inside]
        dists = []
        for p in bowl_pts:
            loc, *_ = hi_bvh.find_nearest(Vector(p))
            if loc:
                dists.append((Vector(p) - loc).length)
        dists = np.array(dists) * 1000
        print(f"{side}: 碗内低模顶点={inside.sum()} 偏差 均值={dists.mean():.3f} 中位={np.median(dists):.3f} P95={np.percentile(dists,95):.3f} 最大={dists.max():.3f}mm")
    print("BOWL_VERIFY_DONE")


if __name__ == "__main__":
    main()
