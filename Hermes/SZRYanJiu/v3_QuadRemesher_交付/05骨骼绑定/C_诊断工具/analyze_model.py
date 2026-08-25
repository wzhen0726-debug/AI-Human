"""分析输入模型几何特征，为骨骼绑定提供关节检测依据。
用法: blender --background <input.blend> --factory-startup --python analyze_model.py
"""
import bpy
import json
from mathutils import Vector

def analyze():
    # 找主体 mesh（面数最多的 mesh，排除眼球）
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    main = None
    main_faces = 0
    for o in meshes:
        m = o.data
        if len(m.polygons) > main_faces:
            main = o
            main_faces = len(m.polygons)

    if main is None:
        print("ERROR: no mesh found")
        return

    mesh = main.data
    verts = [v.co.copy() for v in mesh.vertices]

    # 全局包围盒
    min_co = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_co = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    dims = max_co - min_co
    center = (min_co + max_co) / 2

    print("=" * 60)
    print(f"主体对象: {main.name}")
    print(f"顶点数: {len(mesh.vertices)}")
    print(f"面数: {len(mesh.polygons)}")
    print(f"包围盒 min: {min_co}")
    print(f"包围盒 max: {max_co}")
    print(f"尺寸(X宽, Y厚, Z高): {dims.x:.4f}, {dims.y:.4f}, {dims.z:.4f}")
    print(f"中心: {center}")
    print(f"身高(Z): {dims.z:.4f} m")
    print(f"肩宽(X): {dims.x:.4f} m")
    print(f"身体厚度(Y): {dims.y:.4f} m")

    # Z 高度分布分析：每 1% 高度统计 X 跨距和 max(|X|)
    print("=" * 60)
    print("Z高度分布 (每2%): Z_ratio | X跨距 | maxX | 顶点数")
    H = dims.z
    W = dims.x
    z_min = min_co.z
    for i in range(0, 101, 2):
        z_lo = z_min + H * i / 100.0
        z_hi = z_min + H * (i + 2) / 100.0
        band = [v for v in verts if z_lo <= v.z < z_hi]
        if not band:
            continue
        x_span = max(v.x for v in band) - min(v.x for v in band)
        max_abs_x = max(abs(v.x) for v in band)
        print(f"  {i:3d}%-{i+2:3d}% | {x_span:.4f} | {max_abs_x:.4f} | {len(band)}")

    # 判断姿态：T-pose vs A-pose
    # T-pose: 手臂水平，maxX 出现在肩高 (65%-88%)
    # A-pose: 手臂下垂，maxX 出现在中段
    print("=" * 60)
    print("姿态判断:")
    top_band = [v for v in verts if v.z >= z_min + H * 0.65]
    mid_band = [v for v in verts if z_min + H * 0.30 <= v.z < z_min + H * 0.65]
    top_max_x = max(abs(v.x) for v in top_band) if top_band else 0
    mid_max_x = max(abs(v.x) for v in mid_band) if mid_band else 0
    print(f"  上半身(65%+) maxX = {top_max_x:.4f}")
    print(f"  中段(30%-65%) maxX = {mid_max_x:.4f}")
    if top_max_x > mid_max_x * 1.1:
        print("  → 判定: T-pose (手臂水平)")
    else:
        print("  → 判定: A-pose (手臂下垂)")

    # Y 轴前后分布（判断模型朝向）
    print("=" * 60)
    print(f"Y范围: [{min(v.y for v in verts):.4f}, {max(v.y for v in verts):.4f}]")
    print(f"Y中心: {(min(v.y for v in verts) + max(v.y for v in verts))/2:.4f}")

if __name__ == "__main__":
    analyze()
