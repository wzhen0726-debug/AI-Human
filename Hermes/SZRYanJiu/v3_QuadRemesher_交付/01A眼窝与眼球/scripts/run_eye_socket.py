"""01_1眼窝制作 - 主入口

输入: 01_highpoly_repair.blend
输出: 01_1_eye_socket.blend (含双眼窝, 供02 QR读取)
"""
import bpy, os, sys, math
from mathutils import Vector

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eye_socket_config import *
from iris_detect import detect_iris_centers
from socket_ops import make_eye_socket, make_eye_cup

def load_3ddfa_centers():
    """从3DDFA反投影结果读眼中心 (语义定位, 比暗像素准).
    返回(left_center, right_center) numpy数组, 坐标=角膜表面交点."""
    import json, numpy as np
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = np.array(d["L"]["center_3d"], dtype=np.float32)
    cR = np.array(d["R"]["center_3d"], dtype=np.float32)
    print(f"load_3ddfa_centers: L={cL} R={cR}")
    print(f"  眼间距={np.linalg.norm(cL-cR)*1000:.1f}mm")
    return cL, cR

def fix_socket_normals(obj, side):
    """翻转眼窝开口(眼睑轮廓多边形)内所有朝内的面, 统一朝-Y(朝外/朝眼球).
    压凹把眼睑顶点往+Y推, 面片翻折法线朝内. 只动眼窝内的面, 不全局重算."""
    import bmesh
    from socket_ops import load_eyelid_contour, point_in_polygon
    poly = load_eyelid_contour(side)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    flipped = 0
    for f in bm.faces:
        fc = f.calc_center_median()
        if point_in_polygon(fc.x, fc.z, poly) and f.normal.y > 0:
            f.normal_flip()
            flipped += 1
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"fix_socket_normals {side}: flipped {flipped} faces to face -Y")

def render_shots(filepath_prefix, cL=None, cR=None):
    """渲染头部特写截图到screenshots目录. 有眼中心时对准眼部, 否则对全身中心."""
    os.makedirs(SHOT_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.show_cavity = True
    
    obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
    local_verts = [v.co for v in obj.data.vertices]
    xs, ys, zs = zip(*[(v.x, v.y, v.z) for v in local_verts])
    
    if cL is not None and cR is not None:
        # 头部特写: 对准两眼中心, 视距0.35m
        face_center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))
        center = face_center
        dims = 0.40
    else:
        center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
        dims = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam) if not cam.users_scene else None
    scene.camera = cam
    
    shots = [
        ("front", Vector((center.x, center.y - dims*0.8, center.z)), 0),
        ("side",  Vector((center.x + dims*0.8, center.y, center.z)), math.pi/2),
    ]
    for name, pos, rot in shots:
        cam.location = pos
        look = center - pos
        cam.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"{filepath_prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

def main():
    print("=== 01_1 Eye Socket ===")
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type=='MESH'][0]
    
    # 眼中心来源: 3DDFA语义定位(首选) 或 暗像素法(回退, 已暂停)
    if USE_3DDFA:
        print("Using 3DDFA semantic centers")
        cL, cR = load_3ddfa_centers()
    else:
        print("Using dark-pixel detection (fallback)")
        cL, cR = detect_iris_centers()
    
    # 左眼
    make_eye_socket(obj, cL, "L")
    make_eye_cup(obj, cL, "L")
    # 右眼
    make_eye_socket(obj, cR, "R")
    make_eye_cup(obj, cR, "R")
    
    # 法线校正: 眼窝内所有面朝-Y(朝眼球), 修复压凹翻折+碗面绕向不定
    fix_socket_normals(obj, "L")
    fix_socket_normals(obj, "R")
    
    # 保存
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    
    # 截图 (头部特写, 对准眼中心)
    render_shots("01_1_eye_socket", cL, cR)
    print("=== Done ===")

if __name__ == "__main__":
    main()
