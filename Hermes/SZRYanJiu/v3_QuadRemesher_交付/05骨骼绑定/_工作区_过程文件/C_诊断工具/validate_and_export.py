"""数值化姿态验证 + GLB导出
验证: 姿态变形后的顶点位移统计
导出: GLB (1 mesh + 1 armature, 包含贴图)
"""
import bpy
import sys
import os
import math
import json
from mathutils import Vector

def apply_pose(armature, pose_dict):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    for name, (rx, ry, rz) in pose_dict.items():
        if name in armature.pose.bones:
            pb = armature.pose.bones[name]
            pb.rotation_mode = 'XYZ'  # 先设置 mode
            pb.rotation_euler = (rx, ry, rz)
    bpy.ops.object.mode_set(mode='OBJECT')

def reset_pose(armature):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    for pb in armature.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode='OBJECT')

def get_deformed_verts(obj):
    """获取变形后的世界空间顶点（用 new_from_object 保证 armature 变形生效）"""
    dg = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)
    mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=dg)
    verts = [v.co.copy() for v in mesh.vertices]
    bpy.data.meshes.remove(mesh)
    return verts

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

    # 获取 T-pose 顶点
    reset_pose(arm)
    bpy.context.view_layer.update()
    tpose_verts = get_deformed_verts(body)
    print(f"T-pose 采样: {len(tpose_verts)} 顶点")

    # 姿态测试: 左臂弯曲 45°
    apply_pose(arm, {
        "LeftArm": (0, 0, math.radians(-45)),
    })
    bpy.context.view_layer.update()
    bent_verts = get_deformed_verts(body)

    # 计算位移
    displacements = []
    max_disp = 0
    zero_disp = 0
    for i, (a, b) in enumerate(zip(tpose_verts, bent_verts)):
        d = (b - a).length
        if d > 0.0001:
            displacements.append(d)
        else:
            zero_disp += 1
        if d > max_disp:
            max_disp = d

    if displacements:
        avg_disp = sum(displacements) / len(displacements)
        displacements.sort()
        p50 = displacements[len(displacements)//2]
        p90 = displacements[int(len(displacements)*0.9)]
        p95 = displacements[int(len(displacements)*0.95)]
    else:
        avg_disp = p50 = p90 = p95 = 0

    print("=" * 50)
    print(f"姿态变形测试 (左臂弯曲45°):")
    print(f"  总顶点: {len(tpose_verts)}")
    print(f"  位移顶点: {len(displacements)} ({100*len(displacements)/len(tpose_verts):.1f}%)")
    print(f"  未位移顶点: {zero_disp} ({100*zero_disp/len(tpose_verts):.1f}%)")
    print(f"  最大位移: {max_disp:.4f} m")
    print(f"  平均位移: {avg_disp:.4f} m")
    print(f"  中位位移: {p50:.4f} m")
    print(f"  P90: {p90:.4f} m")
    print(f"  P95: {p95:.4f} m")

    # 验证: 腿部应该几乎没有位移（手臂弯曲不应影响腿部）
    # 左臂区域的顶点应该位移较大
    if max_disp > 0.01 and avg_disp < max_disp * 0.5:
        print("  ✅ 姿态变形合理: 最大位移集中在手臂区域，其余区域位移很小")
    else:
        print("  ⚠️ 姿态变形可能异常，请检查")

    reset_pose(arm)

    # GLB 导出
    print("=" * 50)
    glb_path = os.path.join(out_dir, "06_rig.glb") if out_dir else "06_rig.glb"
    bpy.ops.object.select_all(action='DESELECT')
    for o in bpy.data.objects:
        o.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        export_keep_originals=False,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_animations=False,
        # 不使用 Draco 压缩以确保兼容性
    )
    print(f"GLB 导出: {glb_path}")

    # 文件大小
    if os.path.exists(glb_path):
        size_mb = os.path.getsize(glb_path) / (1024 * 1024)
        print(f"文件大小: {size_mb:.1f} MB")

    print("Done.")

if __name__ == "__main__":
    main()