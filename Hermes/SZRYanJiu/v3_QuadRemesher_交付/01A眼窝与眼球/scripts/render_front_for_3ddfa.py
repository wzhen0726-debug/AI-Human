"""01A - 为3DDFA渲染高模正脸图 + 记录正交相机参数

为什么用正交相机: 像素<->世界坐标是线性映射, 反投影2D关键点回3D最简单精确
(透视相机需要深度才能反投影, 正交相机只需沿视线方向射线求交).

输入: 01_highpoly_repair.blend
输出: face_front.png (1024x1024 正脸) + cam_params.json (反投影用)
"""
import bpy, os, sys, json, math
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
IN_BLEND = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
OUT_DIR = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa")
OUT_PNG = os.path.join(OUT_DIR, "face_front.png")
OUT_CAM = os.path.join(OUT_DIR, "cam_params.json")

RES = 1024            # 渲染分辨率 (正方形, 1024)
ORTHO_SCALE = 0.40    # 正交视宽 40cm (覆盖整脸: 下巴z~1.40到头顶z~1.78, wpp≈0.39mm/pixel)
CAM_DIST = 0.5        # 相机放在脸前 0.5m (-Y侧)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

    # mesh 包围盒中心与范围
    vs = obj.data.vertices
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]; zs = [v.co.z for v in vs]
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    center = Vector((cx, cy, cz))

    # 相机对准头部/脸部中心: 取包围盒z的 88% 高度 (脸中心z≈1.59)
    aim_z = min(zs) + (max(zs)-min(zs))*0.88
    aim = Vector((cx, cy, aim_z))

    # 正交相机, 在脸的 -Y 侧, 看向 +Y (模型面朝 -Y)
    cam_data = bpy.data.cameras.new("3DDFA_Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ORTHO_SCALE
    cam_data.clip_start = 0.01
    cam_data.clip_end = 5.0
    cam = bpy.data.objects.new("3DDFA_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)

    cam_pos = Vector((cx, aim.y - CAM_DIST, aim.z))
    cam.location = cam_pos
    look = aim - cam_pos
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()

    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100

    # Workbench + 贴图 (轻量, 不触发EEVEE着色器编译卡顿)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_specular_highlight = False

    scene.render.filepath = OUT_PNG
    bpy.ops.render.render(write_still=True)
    print(f"rendered: {OUT_PNG}")

    # 记录相机参数 (反投影必需)
    # Blender相机: 视线方向 = 局部-Z, 右 = 局部+X, 上 = 局部+Y
    R = cam.matrix_world
    forward = R @ Vector((0, 0, -1)) - R @ Vector((0, 0, 0))  # 方向
    right = R @ Vector((1, 0, 0)) - R @ Vector((0, 0, 0))
    up = R @ Vector((0, 1, 0)) - R @ Vector((0, 0, 0))
    params = {
        "cam_location": list(cam.location),
        "forward": list(forward.normalized()),
        "right": list(right.normalized()),
        "up": list(up.normalized()),
        "ortho_scale": ORTHO_SCALE,
        "res_x": RES, "res_y": RES,
        "wpp": ORTHO_SCALE / RES,   # 世界米/像素
        "aim": list(aim),
        "note": "正交相机: point_on_plane = cam_loc + right*(px-W/2)*wpp + up*(H/2-py)*wpp; 沿forward射线求交得3D点",
    }
    with open(OUT_CAM, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    print(f"cam params: {OUT_CAM}")
    print(f"wpp={params['wpp']*1000:.4f} mm/pixel")
    print("=== Done ===")

if __name__ == "__main__":
    main()
