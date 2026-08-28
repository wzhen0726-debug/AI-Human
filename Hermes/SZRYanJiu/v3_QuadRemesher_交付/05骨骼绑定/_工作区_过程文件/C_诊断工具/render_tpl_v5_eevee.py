"""EEVEE渲染验证: 确认标记球材质颜色真实存在(用户viewport=Material着色会显示)."""
import bpy, os, math

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
SRC = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_AI预置.blend")
OUT = os.path.join(BASE, "_工作区_过程文件", "screenshots", "arp模板v5_eevee.png")

bpy.ops.wm.open_mainfile(filepath=SRC)
scn = bpy.context.scene
scn.render.engine = 'BLENDER_EEVEE'
scn.render.resolution_x = 900
scn.render.resolution_y = 1350

# 灯光
light_data = bpy.data.lights.new("sun", 'SUN')
light_data.energy = 3.0
light_obj = bpy.data.objects.new("sun", light_data)
light_obj.rotation_euler = (math.radians(50), 0, math.radians(20))
scn.collection.objects.link(light_obj)
# 世界光
if scn.world is None:
    scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
scn.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3

cam = bpy.data.cameras.new("cam")
cam.type = 'ORTHO'
cam.ortho_scale = 4.2   # 加宽: 说明牌在x=-1.75, 3.2宽视野会裁掉
cam_obj = bpy.data.objects.new("cam", cam)
scn.collection.objects.link(cam_obj)
cam_obj.location = (0, -8, 0.95)
cam_obj.rotation_euler = (1.5708, 0, 0)
scn.camera = cam_obj

scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("EEVEE_RENDER_DONE")
# 同时打印每个球的材质颜色(决定性证据)
for o in bpy.data.objects:
    if o.name.endswith("_loc") and not o.name.endswith("_loc_sym"):
        mat = o.data.materials[0] if o.data.materials else None
        if mat and mat.use_nodes:
            bc = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
            print(f"{o.name}: mat={mat.name} rgb=({bc[0]:.2f},{bc[1]:.2f},{bc[2]:.2f})")
