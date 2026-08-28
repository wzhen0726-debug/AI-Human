"""渲染两版行走动画视频 (2026-08-27): 手写版+ARP版 各一个MP4, 放交付目录.
相机: 正面固定机位, 36帧原地走路循环, 1280x720 24fps."""
import bpy, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"

JOBS = [
    # (源blend, 视频输出)
    (os.path.join(BASE, "手写版交付", "04_行走动画测试.blend"),
     os.path.join(BASE, "手写版交付", "06_行走演示.mp4")),
    (os.path.join(BASE, "ARP版交付", "02_ARP绑定.blend"),
     os.path.join(BASE, "ARP版交付", "06_行走演示.mp4")),  # ARP版先试绑定文件
]

bpy.ops.wm.read_factory_settings(use_empty=True)

for src, out in JOBS:
    bpy.ops.wm.open_mainfile(filepath=src)
    scn = bpy.context.scene

    # 找最大mesh(身体)和骨架
    body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices), default=None)
    rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if not body or not rig:
        print(f"SKIP {src}: 无mesh或骨架")
        continue

    # 有没有动画?
    has_anim = rig.animation_data and rig.animation_data.action
    print(f"{os.path.basename(src)}: 动画={has_anim}")

    # 相机: 正面(-Y方向看向模型), 全身入画
    cam_data = bpy.data.cameras.new("WalkCam")
    cam = bpy.data.objects.new("WalkCam", cam_data)
    scn.collection.objects.link(cam)
    cam.location = (0, -3.2, 0.95)
    cam.rotation_euler = (1.5708, 0, 0)   # 水平朝+Y看
    scn.camera = cam

    # 灯光
    key = bpy.data.lights.new("Key", 'SUN')
    key.energy = 3.0
    ko = bpy.data.objects.new("Key", key)
    scn.collection.objects.link(ko)
    ko.rotation_euler = (0.6, 0.2, 0.3)

    # 渲染设置: EEVEE mp4
    scn.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderEngine') and 'BLENDER_EEVEE_NEXT' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
    scn.render.resolution_x = 1280
    scn.render.resolution_y = 720
    scn.render.fps = 24
    scn.frame_start = 1
    scn.frame_end = 36
    scn.render.image_settings.file_format = 'FFMPEG'
    scn.render.ffmpeg.format = 'MPEG4'
    scn.render.ffmpeg.codec = 'H264'
    scn.render.filepath = out

    try:
        bpy.ops.render.render(animation=True)
        print(f"VIDEO_DONE {out}")
    except Exception as e:
        print(f"VIDEO_FAIL {out}: {e}")

print("RENDER_ALL_DONE")
