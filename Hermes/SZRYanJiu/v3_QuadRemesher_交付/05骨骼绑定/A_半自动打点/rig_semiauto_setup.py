"""骨骼绑定半自动打点 v2 — 照 01A 眼窝模板逻辑重做 (2026-08-25)

01A 逻辑 (正确做法):
  1. 初始位置 = 程序测量数据 (measure_joints.py 输出), 用户只需微调
  2. 只标 R 侧 + 中线 (8个点), L 侧由 mirror_rig_markers.py 镜像生成
  3. Empty球体 + show_in_front + 中英文命名 + 颜色分组
差异: 关节点在肢体内部 → 不加Shrinkwrap (01A眼睑点在表面才吸附)

用法: blender -b --python rig_semiauto_setup.py
"""
import bpy, os, json

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BODY = os.path.join(BASE, "04纹理烘焙", "04_bake.blend")
EYEBALL = os.path.join(BASE, "01A眼窝与眼球", "models", "01_2_eyeball_placed.blend")
JOINTS = os.path.join(BASE, "05骨骼绑定", "A_半自动打点", "joints_measured.json")
OUT = os.path.join(BASE, "05骨骼绑定", "A_半自动打点", "06_rig_markers.blend")

joints = json.load(open(JOINTS, encoding="utf-8"))

# 初始标记: 中线3个(不镜像) + R侧5个 (L侧由镜像脚本生成)
# (标记ID, 中文名, 英文名, 颜色, 位置key, 是否中线)
MARKERS = [
    ("HeadTop",  "头顶", "headtop",  (1.0, 0.9, 0.2, 1.0), "HeadTop",    True),
    ("NeckBase", "颈根", "neckbase", (1.0, 0.9, 0.2, 1.0), "NeckBase",   True),
    ("Crotch",   "会阴", "crotch",   (1.0, 0.9, 0.2, 1.0), "Crotch",     True),
    ("Shoulder_R", "右肩", "shoulder_R", (1.0, 0.35, 0.35, 1.0), "Shoulder_R", False),
    ("Elbow_R",    "右肘", "elbow_R",    (1.0, 0.35, 0.35, 1.0), "Elbow_R",    False),
    ("Wrist_R",    "右腕", "wrist_R",    (1.0, 0.35, 0.35, 1.0), "Wrist_R",    False),
    ("Knee_R",   "右膝", "knee_R",   (0.35, 0.9, 0.4, 1.0), "Knee_R",   False),
    ("Ankle_R",  "右踝", "ankle_R",  (0.35, 0.9, 0.4, 1.0), "Ankle_R",  False),
]

# 每个标记的放置指南(唯一体表标志, 不留歧义)
GUIDE = {
    "HeadTop":  "头顶最高点正中",
    "NeckBase": "头颈交界: 下巴抬起的折痕高度, 喉结上方",
    "Crotch":   "两腿分叉正中",
    "Shoulder_R": "右肩: 三角肌中点(手臂外侧肌肉最鼓处中心)",
    "Elbow_R":    "右肘: 肘关节弯曲皱褶中心",
    "Wrist_R":    "右腕: 手掌与手臂交界皱褶中心",
    "Knee_R":   "右膝: 髌骨(膝盖骨)中心",
    "Ankle_R":  "右踝: 踝骨最高点",
}

def main():
    # 1. 加载身体
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=BODY)
    cands = [o for o in bpy.context.scene.objects if o.type == 'MESH' and 'eye' not in o.name.lower()]
    body = max(cands, key=lambda o: len(o.data.polygons))
    print(f"身体: {body.name}")

    # 2. 导入眼球
    if os.path.exists(EYEBALL):
        before = set(bpy.data.objects.keys())
        with bpy.data.libraries.load(EYEBALL, link=False) as (d_from, d_to):
            d_to.objects = [n for n in d_from.objects if 'eye' in n.lower()]
        for o in d_to.objects:
            if o and o.name not in before:
                bpy.context.collection.objects.link(o)
                print(f"眼球: {o.name}")

    # 3. 清旧标记集合
    for cname in ["LM_Rig", "LM_R", "LM_L", "LM_M"]:
        c = bpy.data.collections.get(cname)
        if c:
            for o in list(c.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)

    # 4. 创建标记: 中线点→LM_M(黄色,不镜像), R侧点→LM_R(红色,待镜像)
    coll_m = bpy.data.collections.new("LM_M")
    coll_r = bpy.data.collections.new("LM_R")
    bpy.context.scene.collection.children.link(coll_m)
    bpy.context.scene.collection.children.link(coll_r)
    idx = 0
    for mid, cn, en, color, key, is_mid in MARKERS:
        idx += 1
        x, y, z = joints[key]
        e = bpy.data.objects.new(f"LM_{idx:02d}_{cn}_{en}", None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.012          # 1.2cm, 身体尺度
        e.location = (x, y, z)
        e.show_in_front = True
        e.color = color
        e.show_name = True
        (coll_m if is_mid else coll_r).objects.link(e)
        # 关节在肢体内部 → 不加Shrinkwrap (与01A眼睑表面点的关键差异)
        print(f"  LM_{idx:02d}_{cn}_{en}: ({x:.3f}, {y:.3f}, {z:.3f}) ← {GUIDE[mid]}{' [中线,不镜像]' if is_mid else ''}")

    # 5. 空L侧集合(等待镜像)
    lcoll = bpy.data.collections.new("LM_L")
    bpy.context.scene.collection.children.link(lcoll)

    # 6. 视图: 正视图+实体
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.region_3d.view_perspective = 'ORTHO'
                    space.region_3d.view_rotation = (1.0, 0.0, 0.0, 0.0)
            break

    # 7. 保存
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"\n保存: {OUT}")
    print("=" * 50)
    print("使用步骤 (照01A流程):")
    print("1. Blender 5.1 打开 06_rig_markers.blend")
    print("2. 正视图/侧视图切换, 选中标记点按G微调到指南位置:")
    for mid, cn, en, _, _ in MARKERS:
        print(f"   {cn}: {GUIDE[mid]}")
    print("3. Ctrl+S 保存")
    print("4. 运行 mirror_rig_markers.py 镜像生成L侧")
    print("5. 运行 rig_from_markers.py 生成骨骼+权重+GLB")

if __name__ == "__main__":
    main()
