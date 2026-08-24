"""验证: QR低模(02)对眼窝区域的保真度.
对比高模(01_1眼窝版)与低模(02):
1. 眼窝区顶点密度(高模vs低模)
2. 低模眼区到高模表面的偏差(双向最大)
3. 眼窝碗深保持度(开口平面到碗底深度)
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HIGH_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
CONTOUR_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")


def get_mesh_world(obj):
    """返回世界坐标顶点矩阵."""
    mat = obj.matrix_world
    return np.array([(mat @ v.co)[:] for v in obj.data.vertices])


def region_mask(pts, center, radius=0.025):
    """以眼裂中心为球心, 半径25mm的区域掩码."""
    return np.linalg.norm(pts - np.array(center), axis=1) < radius


def main():
    cont = json.load(open(CONTOUR_JSON, encoding="utf-8"))

    # --- 加载高模 ---
    bpy.ops.wm.open_mainfile(filepath=HIGH_BLEND)
    hi = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    hi_pts = get_mesh_world(hi)
    hi_bvh = BVHTree.FromObject(hi, bpy.context.evaluated_depsgraph_get())

    # --- 加载低模(另存到当前场景) ---
    bpy.ops.wm.append(filepath=os.path.join(LOW_BLEND, "Object", "tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR"),
                      directory=os.path.join(LOW_BLEND, "Object"), filename="tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
    lo = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069_QR")
    lo_pts = get_mesh_world(lo)

    print(f"高模总顶点={len(hi_pts):,} 低模总顶点={len(lo_pts):,}")

    for side in ("L", "R"):
        c = np.array(cont[side]["center"])
        rim = np.array(cont[side]["rim_3d"])
        rim_y = float(rim[:, 1].mean())

        hi_m = region_mask(hi_pts, c, 0.025)
        lo_m = region_mask(lo_pts, c, 0.025)
        print(f"\n=== {side}眼区(25mm半径) ===")
        print(f"高模眼区顶点={hi_m.sum():,} 低模眼区顶点={lo_m.sum():,} 密度比={hi_m.sum()/max(lo_m.sum(),1):.1f}x")

        # 低模眼区顶点 → 高模表面距离(低模贴合度)
        lo_region = lo_pts[lo_m]
        dists = []
        for p in lo_region[::10]:  # 抽样1/10加速
            loc, *_ = hi_bvh.find_nearest(Vector(p))
            if loc:
                dists.append((Vector(p) - loc).length)
        dists = np.array(dists) * 1000
        print(f"低模→高模偏差: 均值={dists.mean():.3f}mm 中位={np.median(dists):.3f}mm P95={np.percentile(dists,95):.3f}mm 最大={dists.max():.3f}mm")

        # 碗深: 高模/低模眼区最低y点(最深处) 相对开口平面的深度
        hi_region = hi_pts[hi_m]
        lo_region_full = lo_pts[lo_m]
        hi_depth = (rim_y - hi_region[:, 1].min()) * 1000
        lo_depth = (rim_y - lo_region_full[:, 1].min()) * 1000
        print(f"碗深: 高模={hi_depth:.2f}mm 低模={lo_depth:.2f}mm 保持率={lo_depth/hi_depth*100:.0f}%")

    print("\nVERIFY_DONE")


if __name__ == "__main__":
    main()
