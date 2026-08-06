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

def render_shots(filepath_prefix):
    """渲染正面特写+侧面截图到screenshots目录"""
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
    
    # 自动检测虹膜中心
    cL, cR = detect_iris_centers()
    
    # 左眼
    make_eye_socket(obj, cL, "L")
    make_eye_cup(obj, cL, "L")
    # 右眼
    make_eye_socket(obj, cR, "R")
    make_eye_cup(obj, cR, "R")
    
    # 保存
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    
    # 截图
    render_shots("01_1_eye_socket")
    print("=== Done ===")

if __name__ == "__main__":
    main()
