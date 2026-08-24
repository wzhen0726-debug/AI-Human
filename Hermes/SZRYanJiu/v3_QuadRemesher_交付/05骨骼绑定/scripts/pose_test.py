"""绑定验证 + 姿态测试 + 截图渲染
验证: 对象结构、权重、姿态变形
"""
import bpy
import sys
import os
import math
from mathutils import Vector

def setup_render():
    """设置渲染场景"""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = 'PNG'

    # 清空场景灯光
    bpy.ops.object.select_all(action='DESELECT')
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            o.select_set(True)
    bpy.ops.object.delete()

    # 添加灯光
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.object
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(45), 0, math.radians(45))

    # 添加相机
    bpy.ops.object.camera_add(location=(0, -4, 1))
    cam = bpy.context.object
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam

def set_pose(armature, pose_dict):
    """设置姿态。pose_dict: {bone_name: (rot_x, rot_y, rot_z) in radians}"""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    for bone_name, (rx, ry, rz) in pose_dict.items():
        if bone_name in armature.pose.bones:
            pb = armature.pose.bones[bone_name]
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler = (rx, ry, rz)
    bpy.ops.object.mode_set(mode='OBJECT')

def render_view(filepath):
    """渲染当前视图"""
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print(f"渲染: {filepath}")

def reset_pose(armature):
    """重置姿态"""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    for pb in armature.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode='OBJECT')

def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    out_dir = None
    for i, arg in enumerate(argv):
        if arg == "--outdir" and i + 1 < len(argv):
            out_dir = argv[i + 1]

    arm = None
    body = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            arm = o
        elif o.type == 'MESH' and 'eye' not in o.name.lower():
            body = o

    if arm is None or body is None:
        print("ERROR: 找不到骨架或body")
        return

    print("=" * 50)
    print("对象结构验证:")
    for o in bpy.data.objects:
        parent_info = f"parent={o.parent.name if o.parent else 'None'}"
        if o.parent_type == 'BONE':
            parent_info += f" (bone={o.parent_bone})"
        print(f"  {o.name}: {o.type}, {parent_info}")

    # 权重检查
    print("=" * 50)
    zero_weight = 0
    total = len(body.data.vertices)
    for v in body.data.vertices:
        has = any(g.weight > 0.001 for g in v.groups)
        if not has:
            zero_weight += 1
    print(f"权重覆盖: {total - zero_weight}/{total} ({100*(total-zero_weight)/total:.1f}%)")

    # 姿态测试
    setup_render()

    # 1. T-pose 渲染
    print("=" * 50)
    print("渲染 T-pose...")
    render_view(os.path.join(out_dir, "tpose_front.png") if out_dir else "tpose_front.png")

    # 2. 手臂下垂 (A-pose)
    set_pose(arm, {
        "LeftArm": (0, 0, math.radians(-60)),
        "RightArm": (0, 0, math.radians(60)),
    })
    print("渲染 A-pose...")
    render_view(os.path.join(out_dir, "apose_front.png") if out_dir else "apose_front.png")
    reset_pose(arm)

    # 3. 腿弯曲
    set_pose(arm, {
        "LeftLeg": (math.radians(30), 0, 0),
        "RightLeg": (math.radians(30), 0, 0),
    })
    print("渲染 腿弯曲...")
    render_view(os.path.join(out_dir, "leg_bend.png") if out_dir else "leg_bend.png")
    reset_pose(arm)

    print("Done.")

if __name__ == "__main__":
    main()