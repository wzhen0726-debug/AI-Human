"""01_2 眼球摆入 - 主脚本

1. 打开01_1眼窝blend
2. 导入eye_01.glb, 拆成左右眼
3. 眼中心来源: 3DDFA语义定位(首选, 角膜表面交点) / 暗像素法(回退)
4. 唇缘前缘y: 从当前blend的眼窝开口边界环自动实测(眼窝按新中心重建后位置会变)
5. 摆入眼窝: x/z=眼中心, y=唇缘前缘+半径-探出量
6. 保存blend + Workbench贴图模式渲染验证图
"""
import bpy, os, sys, math
import numpy as np
from mathutils import Vector, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye_socket_config import CUP_DEPTH   # 碗深(极点反推唇缘用)

def load_3ddfa_centers():
    """从3DDFA反投影结果读眼中心 (语义定位, 角膜表面交点).
    同时读球面拟合的"虚拟原始眼球"球心(更靠后, 是真眼球位置)."""
    import json
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    cL = np.array(d["L"]["center_3d"], dtype=np.float32)
    cR = np.array(d["R"]["center_3d"], dtype=np.float32)
    print(f"load_3ddfa_centers: L={cL} R={cR}")
    print(f"  eye_dist={np.linalg.norm(cL-cR)*1000:.1f}mm")
    return cL, cR

def load_fitted_centers():
    """读球面拟合的虚拟原始眼球球心 (眼球摆入的真基准).
    原始高模眼睛是画出来的鼓包, 眼睑贴着r16.6mm球面塑形.
    球心=拟合center, x/z用3DDFA(更准), y用拟合(决定深度)."""
    import json
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for side in ("L","R"):
        fit = d[side]["fitted_sphere"]["center"]
        c3 = d[side]["center_3d"]
        out[side] = np.array([c3[0], fit[1], c3[2]], dtype=np.float32)  # x/z=3DDFA, y=拟合
        print(f"fitted_center {side}: {out[side]} (角膜前极y={out[side][1]-EYE_RADIUS:.4f})")
    return out["L"], out["R"]

def measure_rim_front_y(center, side, rx=0.013, rz=0.009):
    """从当前blend实测眼窝开口唇缘平面y.

    无缝缝合碗: ring0是共享顶点无开放边, min(y)还会抓到前突的眼睑皮肤(污染).
    确定性做法: 找碗底极点(椭圆深区内y最大=最深入头的顶点), 反推 rim = pole_y - CUP_DEPTH.
    与make_eye_cup的构造严格一致(pole = rim + CUP_DEPTH)."""
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    mesh = obj.data
    nv = len(mesh.vertices)
    import numpy as _np
    V = _np.empty(nv*3, dtype=_np.float32)
    mesh.vertices.foreach_get("co", V)
    V = V.reshape(nv, 3)
    cx, cz = center.x, center.z
    dx = (V[:, 0] - cx) / rx
    dz = (V[:, 2] - cz) / rz
    r2 = dx*dx + dz*dz
    # 碗底深区: 归一化半径<0.6(靠近极点), 且y在眼后20mm内(pole≈rim+12mm; 排除后脑勺表面)
    deep = (r2 < 0.6) & (V[:, 1] > center.y - 0.002) & (V[:, 1] < center.y + 0.020)
    if deep.sum() < 3:
        fb = RIM_FRONT_Y_L if side == "L" else RIM_FRONT_Y_R
        print(f"measure_rim_front_y {side}: WARNING only {deep.sum()} deep verts, fallback {fb:.4f}")
        return fb
    pole_y = float(V[deep, 1].max())
    rim_y = pole_y - CUP_DEPTH
    print(f"measure_rim_front_y {side}: pole_y={pole_y:.4f}, rim_y(pole-CUP_DEPTH)={rim_y:.4f}")
    return rim_y

def import_eyeball():
    """导入eye_01.glb, 返回左右眼mesh对象"""
    bpy.ops.import_scene.gltf(filepath=EYE_GLB)
    imported = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    print(f"imported {len(imported)} meshes: {[o.name for o in imported]}")
    eyeL = [o for o in imported if o.location.x < 0][0]
    eyeR = [o for o in imported if o.location.x > 0][0]
    print(f"  assigned: eyeL={eyeL.name} at x={eyeL.location.x:.4f}, eyeR={eyeR.name} at x={eyeR.location.x:.4f}")
    return eyeL, eyeR

def place_eyeball(eye, iris_center, side):
    """摆入单个眼球. iris_center=眼中心(x/z基准).
    深度(y)基准: 角膜前极对齐原始眼睑apex(LID_APEX_Y), 让眼睑皮肤贴着球面.
    球心y = LID_APEX_Y + EYE_RADIUS (+PUSH_BACK微调)."""
    eye.location = (0, 0, 0)
    eye.rotation_euler = (0, 0, 0)
    eye.rotation_quaternion = (1, 0, 0, 0)
    eye.scale = (EYE_SCALE, EYE_SCALE, EYE_SCALE)
    iris = Vector(iris_center)
    # 球心y直接用iris_center传入的y(拟合球心y), x/z=3DDFA. 只加微调旋钮.
    widen = -EYE_WIDEN if side == "L" else EYE_WIDEN
    target = Vector((iris.x + widen, iris.y + EYE_PUSH_BACK, iris.z))
    eye.location = target
    pupil_local = Vector(PUPIL_LOCAL_DIR).normalized()
    target_dir = Vector((0, -1, 0))
    rot = pupil_local.rotation_difference(target_dir)
    eye.rotation_mode = 'QUATERNION'
    eye.rotation_quaternion = rot
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
                for link in list(links):
                    if link.to_node == bsdf_node and link.to_socket.name == 'Base Color':
                        links.remove(link)
                links.new(img_node.outputs['Color'], bsdf_node.inputs['Base Color'])
                print(f"  {side}: direct connect Image Texture -> Base Color")
    print(f"place_eyeball {side}: loc=({target.x:.4f},{target.y:.4f},{target.z:.4f}) scale={EYE_SCALE}")

def render_verification(cL, cR):
    """渲染正面+特写验证图. EEVEE+三灯(确保可见)"""
    os.makedirs(SHOT_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    # 三灯照明(同render_v39_check.py: AREA灯+朝向面部. 注意不能用SUN——SUN能量单位W/m², 同数值会严重过曝)
    face_center = Vector(((cL[0]+cR[0])/2, min(cL[1], cR[1]), (cL[2]+cR[2])/2))
    for name, loc, energy in [("Key", (0, -1, 0.5), 120), ("Fill", (0.5, 0.3, 0), 40), ("Rim", (0, 1, 0.3), 60)]:
        ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.0
        lo = bpy.data.objects.new(name, ld); lo.location = loc
        look = face_center - Vector(loc)
        lo.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(lo)
    # 环境光
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
        bg.inputs['Strength'].default_value = 0.8
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    shots = [
        ("front", Vector((face_center.x, face_center.y - 0.30, face_center.z))),
        ("close", Vector((face_center.x, face_center.y - 0.12, face_center.z))),
    ]
    cam.data.lens = 85  # 长焦特写
    for name, pos in shots:
        cam.location = pos
        look = face_center - pos
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"01_2_eyeball_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"shot: {scene.render.filepath}")

def main():
    print("=== 01_2 Eyeball Placement ===")
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    if USE_3DDFA:
        print("Using fitted-sphere centers (x/z=3DDFA, y=fitted virtual eyeball)")
        cL, cR = load_fitted_centers()   # 球心=拟合虚拟原始眼球(侧视图证实的真位置)
    else:
        print("Using dark-pixel IRIS_L/IRIS_R (fallback)")
        cL = np.array(IRIS_L, dtype=np.float32)
        cR = np.array(IRIS_R, dtype=np.float32)
    eyeL, eyeR = import_eyeball()
    place_eyeball(eyeL, cL, "L")
    place_eyeball(eyeR, cR, "R")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    render_verification(cL, cR)
    print("=== Done ===")

if __name__ == "__main__":
    main()
