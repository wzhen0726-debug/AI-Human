"""诊断: 碗内偏差最大的点在哪里(碗底/碗壁/rim边缘)."""
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
        inside = np.array([point_in_poly(p[0], p[2], poly) for p in lo_pts])
        bowl_idx = np.where(inside)[0]
        rows = []
        for i in bowl_idx:
            p = lo_pts[i]
            loc, *_ = hi_bvh.find_nearest(Vector(p))
            if loc:
                d = (Vector(p) - loc).length * 1000
                rows.append((d, p))
        rows.sort(key=lambda r: -r[0])
        print(f"=== {side}: 碗内{len(rows)}点, 最差5个 ===")
        for d, p in rows[:5]:
            depth = (rim_y - p[1]) * 1000
            rad = np.sqrt((p[0]-c[0])**2 + (p[2]-c[2])**2) * 1000
            print(f"  偏差{d:.2f}mm @ 深度{depth:.1f}mm 径向{rad:.1f}mm")
        ds = np.array([r[0] for r in rows])
        print(f"  分布: <0.5mm={int((ds<0.5).sum())} 0.5-1={int(((ds>=0.5)&(ds<1)).sum())} 1-2={int(((ds>=1)&(ds<2)).sum())} >2={int((ds>=2).sum())}")
    print("DIAG_DONE")


if __name__ == "__main__":
    main()
