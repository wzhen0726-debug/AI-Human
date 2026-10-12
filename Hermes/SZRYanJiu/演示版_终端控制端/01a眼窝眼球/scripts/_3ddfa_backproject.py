"""Backproject 3DDFA ldm68 eye landmarks to 3D on the head mesh (replica of backproject_3ddfa.py, parameterized).

Usage: blender -b --factory-startup -noaudio --python-exit-code 1 --python backproject.py -- <IN_BLEND> <CAM_JSON> <NPY> <OUT_JSON>
Identical unprojection + robust multi-ray normal voting as the original.
"""
import bpy, os, sys, json
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
IN_BLEND, CAM_JSON, NPY, OUT_JSON = argv[0], argv[1], argv[2], argv[3]

def main():
    with open(CAM_JSON, encoding="utf-8") as f:
        cam = json.load(f)
    from mathutils import Vector
    cam_loc = Vector(cam["cam_location"])
    fwd = Vector(cam["forward"])
    right = Vector(cam["right"])
    up = Vector(cam["up"])
    wpp = cam["wpp"]
    W, H = cam["res_x"], cam["res_y"]

    d = np.load(NPY, allow_pickle=True).item()
    ldm = d["ldm68"]
    eye_a = ldm[36:42]   # screen-left eye -> world x<0 -> model L
    eye_b = ldm[42:48]   # screen-right eye -> model R

    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

    def unproject(px, py):
        P = cam_loc + right * ((px - W/2) * wpp) + up * ((H/2 - py) * wpp)
        origin = P - fwd * 0.05
        hit, loc, normal, idx = obj.ray_cast(origin, fwd)
        if not hit:
            return None
        return (loc, normal)

    def unproject_robust(px, py):
        cand = []
        for dx, dy in [(0,0),(2,0),(-2,0),(0,2),(0,-2),(2,2),(-2,2),(2,-2),(-2,-2)]:
            r = unproject(px+dx, py+dy)
            if r is not None:
                cand.append(r)
        if not cand:
            return None
        best = min(cand, key=lambda r: -r[1].dot(Vector((0,-1,0))))
        return best

    result = {}
    for name, pts in [("L", eye_a), ("R", eye_b)]:
        center_px = pts.mean(0)
        r = unproject_robust(*center_px)
        if r is None:
            print(f"{name}: center raycast MISS at px={center_px}")
            continue
        loc, normal = r
        corners = []
        for cp in [pts[0], pts[3]]:
            cr = unproject(*cp)
            corners.append(list(cr[0]) if cr else None)
        result[name] = {
            "center_px": [float(center_px[0]), float(center_px[1])],
            "center_3d": [loc.x, loc.y, loc.z],
            "normal": [normal.x, normal.y, normal.z],
            "corner0_3d": corners[0],
            "corner3_3d": corners[1],
        }
        print(f"{name}: px=({center_px[0]:.1f},{center_px[1]:.1f}) -> "
              f"3D=({loc.x:.4f},{loc.y:.4f},{loc.z:.4f}) normal=({normal.x:.2f},{normal.y:.2f},{normal.z:.2f})")

    if "L" in result and "R" in result:
        cL = np.array(result["L"]["center_3d"]); cR = np.array(result["R"]["center_3d"])
        print(f"眼间距(3D): {np.linalg.norm(cL-cR)*1000:.1f} mm")
        print(f"高度差: {abs(cL[2]-cR[2])*1000:.2f} mm")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"saved: {OUT_JSON}")
    print("=== Done ===")

main()
