"""01_2 眼球摆入 - 主脚本

1. 打开01_1眼窝blend
2. 导入eye_01.glb, 拆成左右眼
3. 摆入眼窝: 位置=虹膜中心沿-Y内缩10mm, 朝向=瞳孔+Z对准全局-Y
4. 保存blend + 渲染验证图
"""
import bpy, os, sys, math
import numpy as np
from mathutils import Vector, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

def import_eyeball():
    """导入eye_01.glb, 返回左右眼mesh对象"""
    bpy.ops.import_scene.gltf(filepath=EYE_GLB)
    imported = [o for o in bpy.context.selected_objects if o.type=='MESH']
    print(f"imported {len(imported)} meshes: {[o.name for o in imported]}")
    
    # GLB命名与位置相反: Eye_L在x>0(实际是右眼), Eye_R在x<0(实际是左眼)
    # 按位置分配: x<0是左眼, x>0是右眼
    eyeL = [o for o in imported if o.location.x < 0][0]  # 左眼 (实际是Eye_R)
    eyeR = [o for o in imported if o.location.x > 0][0]  # 右眼 (实际是Eye_L)
    print(f"  assigned: eyeL={eyeL.name} at x={eyeL.location.x:.4f}, eyeR={eyeR.name} at x={eyeR.location.x:.4f}")
    return eyeL, eyeR

def place_eyeball(eye, opening_center, side):
    """摆入单个眼球"""
    # 1. 先重置到原点(消除GLB原始偏移)
    eye.location = (0, 0, 0)
    eye.rotation_euler = (0, 0, 0)
    eye.rotation_quaternion = (1, 0, 0, 0)
    eye.scale = (1, 1, 1)
    
    # 2. 缩放
    eye.scale = (EYE_SCALE, EYE_SCALE, EYE_SCALE)
    
    # 3. 位置: 几何定参. 模型面朝-Y(前方=y减小), 头内=+Y(y增大).
    # 角膜要探出唇缘 CORNEA_PROTRUDE, 唇缘在最前(y最小).
    # 角膜最前极 = 球心y - 半径. 要求: 球心y - 半径 = 唇缘y - 探出量
    # => 球心y = 唇缘y + 半径 - 探出量  (+Y往头内退)
    # GLB眼球局部中心y=-0.0021(-2.1mm偏移), 需补偿+0.0021
    opening = Vector(opening_center)
    ball_center_y = opening.y + (EYE_RADIUS * EYE_SCALE - CORNEA_PROTRUDE)
    target = Vector((opening.x, ball_center_y + 0.0021, opening.z))
    eye.location = target
    
    # 4. 朝向: 瞳孔+Z对准全局-Y
    pupil_local = Vector(PUPIL_LOCAL_DIR).normalized()
    target_dir = Vector((0, -1, 0))
    rot = pupil_local.rotation_difference(target_dir)
    eye.rotation_mode = 'QUATERNION'
    eye.rotation_quaternion = rot
    
    # 5. 强制材质显示贴图(直接连Image Texture到Base Color, 绕过Mix)
    if eye.data.materials:
        mat = eye.data.materials[0]
        if mat.use_nodes:
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            img_node = None
            bsdf_node = None
            for node in nodes:
                if node.type == 'TEX_IMAGE':
                    img_node = node
                elif node.type == 'BSDF_PRINCIPLED':
                    bsdf_node = node
            if img_node and bsdf_node:
                # 移除所有到Base Color的连接
                for link in list(links):
                    if link.to_node == bsdf_node and link.to_socket.name == 'Base Color':
                        links.remove(link)
                # 直接连接
                links.new(img_node.outputs['Color'], bsdf_node.inputs['Base Color'])
                print(f"  {side}: direct connect Image Texture -> Base Color")
    
    print(f"place_eyeball {side}: loc=({target.x:.4f},{target.y:.4f},{target.z:.4f}) scale={EYE_SCALE}")

def render_verification():
    """渲染正面+侧面验证图"""
    os.makedirs(SHOT_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    
    # EEVEE需要灯光
    if not bpy.data.objects.get("Sun"):
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(45), 0, 0)
        scene.collection.objects.link(sun)
    
    # 面部中心
    cL = Vector(IRIS_L)
    cR = Vector(IRIS_R)
    face_center = (cL + cR) / 2
    
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    
    shots = [
        ("front", Vector((face_center.x, face_center.y - 0.15, face_center.z))),
        ("side",  Vector((face_center.x + 0.15, face_center.y, face_center.z))),
        ("close", Vector((face_center.x, face_center.y - 0.08, face_center.z))),
    ]
    for name, pos in shots:
        cam.location = pos
        look = face_center - pos
        cam.rotation_euler = look.to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"01_2_eyeball_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

def main():
    print("=== 01_2 Eyeball Placement ===")
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    
    # 导入眼球
    eyeL, eyeR = import_eyeball()
    
    # 摆入左眼 (用开口中心)
    place_eyeball(eyeL, OPENING_L, "L")
    # 摆入右眼 (用开口中心)
    place_eyeball(eyeR, OPENING_R, "R")
    
    # 保存
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    
    # 渲染验证
    render_verification()
    print("=== Done ===")

if __name__ == "__main__":
    main()
