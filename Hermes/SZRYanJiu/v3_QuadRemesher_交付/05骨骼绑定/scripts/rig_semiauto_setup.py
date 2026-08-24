"""骨骼绑定半自动打点 - 初始化脚本 (01a模式)
参照: place_eyelid_markers.py

在身体模型上放置13个标记点(Empty球体+Shrinkwrap吸附表面).
用户打开blend后直接选中标记点→按G拖动→Ctrl+S保存.
标记点始终贴合模型表面, show_in_front穿模可见.

用法:
  blender --background --factory-startup --python rig_semiauto_setup.py
"""
import bpy, os, sys
from mathutils import Vector

# 路径: 脚本在 05骨骼绑定/scripts/, 交付根目录 = 上上上级
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BODY = os.path.join(BASE, "04纹理烘焙", "04_bake.blend")
EYEBALL = os.path.join(BASE, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
OUT = os.path.join(BASE, "05骨骼绑定", "06_rig_markers.blend")

# 13个标记点: (id, 中文名, 颜色RGBA, 初始位置(x,y,z))
MARKERS = [
    # 中线(黄色)
    ("HeadTop",  "头顶", (1.0, 0.9, 0.2, 1.0), (0, 0, 1.79)),
    ("NeckBase", "颈根", (1.0, 0.9, 0.2, 1.0), (0, 0, 1.48)),
    ("Crotch",   "会阴", (1.0, 0.9, 0.2, 1.0), (0, 0, 0.90)),
    # 左臂(红色)
    ("Shoulder_L", "左肩", (1.0, 0.35, 0.35, 1.0), (0.14, 0, 1.43)),
    ("Elbow_L",    "左肘", (1.0, 0.35, 0.35, 1.0), (0.36, 0, 1.43)),
    ("Wrist_L",    "左腕", (1.0, 0.35, 0.35, 1.0), (0.59, 0, 1.43)),
    # 右臂(蓝色)
    ("Shoulder_R", "右肩", (0.35, 0.5, 1.0, 1.0), (-0.14, 0, 1.43)),
    ("Elbow_R",    "右肘", (0.35, 0.5, 1.0, 1.0), (-0.36, 0, 1.43)),
    ("Wrist_R",    "右腕", (0.35, 0.5, 1.0, 1.0), (-0.59, 0, 1.43)),
    # 左腿(绿色)
    ("Knee_L",  "左膝", (0.35, 0.9, 0.4, 1.0), (0.14, 0, 0.36)),
    ("Ankle_L", "左踝", (0.35, 0.9, 0.4, 1.0), (0.14, 0, 0.09)),
    # 右腿(橙色)
    ("Knee_R",  "右膝", (0.9, 0.6, 0.3, 1.0), (-0.14, 0, 0.36)),
    ("Ankle_R", "右踝", (0.9, 0.6, 0.3, 1.0), (-0.14, 0, 0.09)),
]


def main():
    # 1. 加载身体模型
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=BODY)
    obj = [o for o in bpy.context.scene.objects if o.type == 'MESH' and 'eye' not in o.name.lower()]
    if not obj:
        print("ERROR: 找不到身体网格")
        return
    body = obj[0]
    print(f"身体网格: {body.name}")

    # 确保模型原点在脚底
    (x_min, y_min, z_min), (x_max, y_max, z_max) = get_bbox(body)
    if z_min > 0.001:
        body.location.z -= z_min
        bpy.context.view_layer.update()
        (x_min, y_min, z_min), (x_max, y_max, z_max) = get_bbox(body)

    # 2. 导入眼球
    if os.path.exists(EYEBALL):
        with bpy.data.libraries.load(EYEBALL, link=False) as (d_from, d_to):
            d_to.objects = [n for n in d_from.objects if 'eye' in n.lower()]
        for o in d_to.objects:
            if o:
                bpy.context.collection.objects.link(o)
                print(f"导入眼球: {o.name}")

    # 3. 清除旧标记集合
    if "LM_Rig" in bpy.data.collections:
        for o in list(bpy.data.collections["LM_Rig"].objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(bpy.data.collections["LM_Rig"])

    coll = bpy.data.collections.new("LM_Rig")
    bpy.context.scene.collection.children.link(coll)

    # 4. 创建标记点 (参照01a: Empty球体+Shrinkwrap)
    for mid, cname, color, init_pos in MARKERS:
        x, y, z = init_pos
        # 如果初始位置在模型外, 调整到模型附近
        x = max(x_min, min(x_max, x))
        y = max(y_min, min(y_max, y))
        z = max(z_min, min(z_max, z))

        e = bpy.data.objects.new(f"LM_{mid}_{cname}", None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.015  # 比01a大(01a是0.0025, 用于眼睛; 身体用0.015)
        e.location = (x, y, z)
        e.show_in_front = True
        e.color = color
        e.show_name = True
        coll.objects.link(e)

        # Shrinkwrap约束: 吸附到身体表面 (参照01a)
        sw = e.constraints.new(type='SHRINKWRAP')
        sw.target = body
        sw.shrinkwrap_type = 'NEAREST_SURFACE'
        sw.distance = 0.0

    print(f"创建 {len(MARKERS)} 个标记点, 集合 LM_Rig")

    # 5. 设置视图(正视图+实体模式)
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.shading.color_type = 'TEXTURE'
                    # 切换到正视图
                    space.region_3d.view_perspective = 'ORTHO'
                    space.region_3d.view_rotation = (1.0, 0.0, 0.0, 0.0)  # 正视图
            break

    # 6. 保存
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"保存: {OUT}")
    print()
    print("=== 使用说明 ===")
    print("1. 用 Blender 5.2 打开此 blend 文件")
    print("2. 在3D视图中选中标记点(彩色小球) → 按 G 拖动到正确关节位置")
    print("3. (标记点自动吸附在模型表面, 穿模可见)")
    print("4. 全部放好后 → Ctrl+S 保存")
    print("5. 运行 rig_from_markers.py 生成骨骼+权重+GLB")


def get_bbox(obj):
    mesh = obj.data
    world = obj.matrix_world
    verts = [world @ v.co for v in mesh.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


if __name__ == "__main__":
    main()