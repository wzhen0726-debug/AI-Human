"""01A - 3DDFA眼部2D关键点反投影回3D网格

原理(正交相机, 线性映射):
  pixel(px,py)[左上原点] -> 相机平面点 P = cam_loc + right*(px-W/2)*wpp + up*(H/2-py)*wpp
  沿 forward(+Y) 射线求交 mesh 表面 -> 3D眼部点(角膜表面)

输入: cam_params.json + face_front.npy(3DDFA输出)
输出: iris_3ddfa.json (左右眼3D中心 + 眼角点, 供eyeball_config使用)
"""
import bpy, os, json
import numpy as np

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
DD_DIR = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa")
NPY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\3DDFA-V3\results_highpoly\face_front\face_front.npy"
OUT_JSON = os.path.join(DD_DIR, "iris_3ddfa.json")

def main():
    with open(os.path.join(DD_DIR, "cam_params.json"), encoding="utf-8") as f:
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
    # ldm68: 右眼36-41, 左眼42-47 (图像: 36=外眼角,42=内眼角 对画面左侧的眼)
    # 注意: 画面左侧(x小)=世界x负=模型右眼... 但3DDFA的36-41定义是"图像左边的眼"
    eye_a = ldm[36:42]   # 画面左侧的眼
    eye_b = ldm[42:48]   # 画面右侧的眼
    # 画面左侧 x<512 -> 世界x<0 -> 模型左眼(x负). 画面右侧 -> 模型右眼.
    # (模型面朝-Y, 从相机看: 画面左=世界x负方向)

    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

    def unproject(px, py):
        """像素->相机平面点->射线求交mesh表面"""
        P = cam_loc + right * ((px - W/2) * wpp) + up * ((H/2 - py) * wpp)
        # 射线起点再往前退一点确保在mesh外
        origin = P - fwd * 0.05
        hit, loc, normal, idx = obj.ray_cast(origin, fwd)
        if not hit:
            return None
        return (loc, normal)

    def unproject_robust(px, py):
        """多射线投票: 中心+邻域8点, 选法线最朝前(-Y=角膜朝向)的命中.
        原因: 眼窝凹陷边缘, 单根射线可能被上睑/睑缘拦截(法线朝-Z朝上),
        角膜表面法线应接近-Y(朝相机). 选最朝前的即真角膜点."""
        cand = []
        for dx, dy in [(0,0),(2,0),(-2,0),(0,2),(0,-2),(2,2),(-2,2),(2,-2),(-2,-2)]:
            r = unproject(px+dx, py+dy)
            if r is not None:
                cand.append(r)
        if not cand:
            return None
        # 法线与-Y夹角最小(最朝前)的命中=角膜
        best = min(cand, key=lambda r: -r[1].dot(Vector((0,-1,0))))
        return best

    result = {}
    for name, pts in [("L", eye_a), ("R", eye_b)]:
        center_px = pts.mean(0)
        # 眼中心 (鲁棒版: 多射线选法线最朝前的角膜命中)
        r = unproject_robust(*center_px)
        if r is None:
            print(f"{name}: center raycast MISS at px={center_px}")
            continue
        loc, normal = r
        # 内外眼角 (用于眼宽验证)
        corners = []
        for cp in [pts[0], pts[3]]:  # 68点: 36/42=外眼角, 39/45=内眼角
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

    # 眼间距验证
    if "L" in result and "R" in result:
        cL = np.array(result["L"]["center_3d"]); cR = np.array(result["R"]["center_3d"])
        print(f"眼间距(3D): {np.linalg.norm(cL-cR)*1000:.1f} mm")
        print(f"高度差: {abs(cL[2]-cR[2])*1000:.2f} mm")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"saved: {OUT_JSON}")
    print("=== Done ===")

if __name__ == "__main__":
    main()
