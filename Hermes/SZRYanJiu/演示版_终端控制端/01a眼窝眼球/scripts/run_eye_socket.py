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
from socket_ops import make_eye_socket, make_eye_cup, finish_socket_boolean

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
    
    # v63/v64: boolean切割模式 → make_eye_socket 已切出 pit(开口=手描轮廓精确), 收尾走 finish_socket_boolean;
    #           v64 掏空模式(SOCKET_EMPTY_INTERIOR=True)则只留 rim 环+空腔, 不做材质分区/UV重映射;
    #           洪泛模式仍用 make_eye_cup 建碗.
    _empty = (SOCKET_CUT_MODE == "boolean" and SOCKET_EMPTY_INTERIOR)
    if _empty:
        _finish = None
        print("开孔模式: boolean 掏空环内(v64) — 只保留 rim 环+空腔, 不做材质分区/UV")
    else:
        _finish = finish_socket_boolean if SOCKET_CUT_MODE == "boolean" else make_eye_cup
        print(f"开孔模式: {SOCKET_CUT_MODE} (收尾={_finish.__name__})")
    # 2026-09-22 (用户方案A): 按眼【门控】选谐波 K —— 从高到低逐档试，只有 rim 带重建得到单一闭环才采用该 K；
    #   失败则回滚到该眼操作前的网格快照，换更小的 K。收益: 每只眼拿到"它能承受的最大 K"(最贴手描轮廓)，
    #   且不会像直接收紧区间那样把某只眼的 rim 带重建搞崩(实测 R 眼在 K=4 时连续 6 轮拿不到单一闭环)。
    _gate_sel = {}
    def _gated_eye(c, side):
        if not globals().get('RIM_CONTOUR_K_GATE', False):
            make_eye_socket(obj, c, side)
            return None
        snap = obj.data.copy()
        snap.name = f"_gate_snap_{side}"
        hi = int(RIM_CONTOUR_K_GATE_HI)
        lo = max(2, int(RIM_CONTOUR_K_FLOOR))
        chosen = None
        for K in range(hi, lo - 1, -1):
            if K != hi:
                obj.data = snap.copy()
                obj.data.name = f"_gate_try_{side}_K{K}"
            ok = make_eye_socket(obj, c, side, k_override=K)
            print(f"[门控] {side}: K={K} → rim带重建 {'通过' if (ok is True or ok is None) else '失败(回滚换小K)'}")
            if ok is True or ok is None:
                chosen = K
                break
        if chosen is None:
            print(f"[门控] {side}: K={lo}..{hi} 全部失败 → 保留 K={lo} 的结果(⚠ 需人工看图确认)")
            chosen = lo
        _gate_sel[side] = chosen
        print(f"[门控] {side}: 采用谐波 K={chosen}")
        return chosen

    # 左眼
    _gated_eye(cL, "L")
    if _finish: _finish(obj, cL, "L")
    # 右眼
    _gated_eye(cR, "R")
    if _finish: _finish(obj, cR, "R")
    if _gate_sel:
        print(f"[门控] 最终选择: {_gate_sel}")
    # 清掉门控/QA 遗留的孤立 mesh 数据块
    try:
        for _m in list(bpy.data.meshes):
            if _m.users == 0 and (_m.name.startswith("_gate") or _m.name.startswith("_rimQA")):
                bpy.data.meshes.remove(_m)
    except Exception:
        pass
    
    # v31: 删custom_normal属性 + 眼窝区局部recalc(皮肤参考). 绝不全局recalc/质心翻转.
    unify_normals_global(obj, cL, cR)

    # v39: UV分配已在make_eye_cup内完成(防止被update_edit_mesh覆盖), 这里不再重复分配.

    # 保存
    # 存盘前切回对象模式(否则文件会以编辑模式保存)
    try:
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"Saved: {OUT_BLEND}")
    
    # 截图 (头部特写, 对准眼中心)
    render_shots("01_1_eye_socket", cL, cR)
    print("=== Done ===")

if __name__ == "__main__":
    main()
