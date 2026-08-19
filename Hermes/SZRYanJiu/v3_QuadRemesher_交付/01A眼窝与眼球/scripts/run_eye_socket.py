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

def unify_normals_global(obj, cL, cR):
    """v31(2026-08-13): 面朝向问题的最终修复.
    根因链(已用控制实验证实):
    1. FBX导入带custom_normal属性(INT16_2D CORNER) → Blender显示/渲染/Face Orientation着色
       用custom normal, 不反映真实绕序.
    2. bmesh新建碗面的corner在该属性上是零向量 → 着色发黑破碎 → 用户看到的"面朝向反了".
    3. 之前所有normal_flip/reverse_faces只改绕序不改custom normal → 显示毫无变化 → "修了没效果".
    4. 控制实验: 输入模型绕序与FBX corner normals吻合99.99% → 绕序本来就对, 不需全局翻转.
       全局recalc(非流形边破坏传播, 恶化3倍)和质心规则(翻转42万合法悬垂面)都是破坏性的.
       带任意区域边界的局部recalc也会把碗从皮肤锚点切断→重翻31/12面(v31实测).
    修复: 只删custom_normal属性(让绕序说了算). 碗面朝向由make_eye_cup内的局部recalc保证
    (碗面+ring0邻接皮肤三角面, 拓扑连通, 传播正确)."""
    me = obj.data
    attr = me.attributes.get('custom_normal')
    if attr:
        me.attributes.remove(attr)
        print("unify_normals: removed custom_normal attribute (winding 99.99% correct, no flip)")
    sharp = me.attributes.get('sharp_face')
    if sharp:
        for i in range(len(sharp.data)):
            sharp.data[i].value = False

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
    
    # v31: 先移除FBX custom_normal属性, 让后续所有法线操作基于真实绕序.
    attr = obj.data.attributes.get('custom_normal')
    if attr:
        obj.data.attributes.remove(attr)
        print("main: removed custom_normal attribute at load")
    
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
    
    # v31: 删custom_normal属性 + 眼窝区局部recalc(皮肤参考). 绝不全局recalc/质心翻转.
    unify_normals_global(obj, cL, cR)

    # v39: UV分配已在make_eye_cup内完成(防止被update_edit_mesh覆盖), 这里不再重复分配.

    # 保存
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    
    # 截图 (头部特写, 对准眼中心)
    render_shots("01_1_eye_socket", cL, cR)
    print("=== Done ===")

if __name__ == "__main__":
    main()
