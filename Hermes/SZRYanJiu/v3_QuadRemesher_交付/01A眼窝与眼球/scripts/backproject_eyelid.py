"""01A - 3DDFA眼睑轮廓反投影, 得到真实杏仁形眼窝开口
用ldm68的6点/眼(外眦-上睑x2-内眦-下睑x2)反投影回3D, 得到真实眼形边界.
输出: eyelid_contour.json {L: {rim_3d: [[x,y,z]x6], width_mm, height_mm, aspect}, R: {...}}
"""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

NPY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\3DDFA-V3\results_highpoly\face_front\face_front.npy"
CAM_JSON = os.path.join(SHOT_DIR, "3ddfa", "cam_params.json")
OUT_JSON = os.path.join(SHOT_DIR, "3ddfa", "eyelid_contour.json")

def main():
    print("=== eyelid contour backproject ===")
    d = np.load(NPY, allow_pickle=True).item()
    ldm68 = d["ldm68"]
    cam = json.load(open(CAM_JSON, encoding="utf-8"))
    cam_loc = Vector(cam["cam_location"])
    right = Vector(cam["right"]); up = Vector(cam["up"]); fwd = Vector(cam["forward"])
    W = cam["res_x"]; H = cam["res_y"]; wpp = cam["wpp"]

    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
    from mathutils.bvhtree import BVHTree
    verts = [v.co[:] for v in obj.data.vertices]
    polys = [tuple(p.vertices) for p in obj.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)

    def raycast(px, py):
        P = cam_loc + right*((px-W/2)*wpp) + up*((H/2-py)*wpp)
        origin = P - fwd*0.05
        loc, nrm, idx, dist = bvh.ray_cast(origin, fwd)
        return np.array(loc) if loc else None

    out = {}
    for side, idx in [("L", range(36,42)), ("R", range(42,48))]:
        pts2d = ldm68[list(idx)]  # 6点: 外眦,上睑,上睑,内眦,下睑,下睑
        rim = []
        for px, py in pts2d:
            hit = raycast(px, py)
            rim.append(hit.tolist() if hit is not None else None)
        # 眼形尺寸(用2D点换算)
        w_mm = (pts2d[:,0].max()-pts2d[:,0].min())*wpp*1000
        h_mm = (pts2d[:,1].max()-pts2d[:,1].min())*wpp*1000
        # 中心=6点3D均值
        valid = [r for r in rim if r is not None]
        center = np.array(valid).mean(0).tolist() if valid else None
        out[side] = {"rim_3d": rim, "width_mm": float(w_mm), "height_mm": float(h_mm),
                     "aspect": float(w_mm/h_mm), "center": center}
        print(f"{side}: {w_mm:.1f}x{h_mm:.1f}mm aspect={w_mm/h_mm:.2f} rim_pts={len(valid)}/6")
        for i,r in enumerate(rim):
            print(f"   pt{i}: {np.round(r,4) if r else None}")
    json.dump(out, open(OUT_JSON,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Saved: {OUT_JSON}")

main()
