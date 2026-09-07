import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付\05骨骼绑定\ARP新版测试_20260831\04_动作测试.blend")
scn = bpy.context.scene
arm = bpy.data.objects['MixamoSkeleton']
LOGS = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\logs"

# 加灯光
ld = bpy.data.lights.new("K", type='AREA'); ld.energy = 400; ld.size = 3
lo = bpy.data.objects.new("K", ld); lo.location = (-3, -3, 2); scn.collection.objects.link(lo)
lo.rotation_euler = (1.2, 0, -0.8)
scn.world.use_nodes = True
bg = scn.world.node_tree.nodes.get("Background")
if bg: bg.inputs['Strength'].default_value = 0.6

cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd)
scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.2

# 渲染帧1(行走开始)、帧18(行走中段)、帧10(跑步)
for act, fr, tag, loc in [
    ('Standard Walk', 1, '04_walk_f1', (-3.2, 0, 1.0)),
    ('Standard Walk', 18, '04_walk_f18', (-3.2, 0, 1.0)),
    ('Running', 10, '04_run_f10', (-3.2, 0, 1.0)),
]:
    arm.animation_data.action = bpy.data.actions[act]
    scn.frame_set(fr); bpy.context.view_layer.update()
    cam.location = loc; cam.rotation_euler = (1.5708, 0, -1.5708)
    scn.render.engine = 'BLENDER_EEVEE'
    scn.render.resolution_x = 512; scn.render.resolution_y = 720
    scn.render.filepath = LOGS + f"\\{tag}.jpg"
    bpy.ops.render.render(write_still=True)
    print(f"saved {tag}")
print("RENDER_DONE")
