# 面朝向叠加核验 (与 Blender face-orientation overlay 同义)
#
# 为什么独立成脚本: 修复这类翻面 bug 时, 修复判据与验证判据很容易同源(例如都用"共顶点邻面平均法线"),
# 结果两边都报"没问题"而用户一眼看到一圈红。本脚本用与叠加显示同义的判据(正视相机下法线朝后 +Y = 红),
# 与修复逻辑完全无关, 专用于事后核验。
#
# 用法:
#   blender -b --factory-startup --python face_orientation_overlay.py -- <blend> [cx cy cz] [outdir]
# 说明:
#   cx cy cz = 关心的区域中心(世界坐标, 米); 只看眼区就传眼中心。缺省 (0,-0.1,1.67)。
# 输出:
#   <outdir>/fo_front.png, <outdir>/fo_low.png  蓝=法线朝前(正常) 红=法线朝后(反面)
#   stdout: 按"到中心的 XZ 距离"分档的红面数 + 总面积(零面积退化面会被单独标出)。
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: -- <blend> [cx cy cz] [outdir]")
    sys.exit(0)
blend = argv[0]
cx, cy, cz = (float(argv[1]), float(argv[2]), float(argv[3])) if len(argv) >= 4 else (0.0, -0.1, 1.67)
outdir = argv[4] if len(argv) > 4 else os.path.dirname(os.path.abspath(blend))

bpy.ops.wm.open_mainfile(filepath=blend)
head = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
if bpy.context.mode != 'OBJECT':
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.mode_set(mode='OBJECT')
me = head.data
for m, col in ((0, (0.25, 0.45, 1.0, 1.0)), (1, (1.0, 0.05, 0.05, 1.0))):
    if len(me.materials) <= m:
        me.materials.append(bpy.data.materials.new(f"FO{m}"))
    me.materials[m].diffuse_color = col

# 判据: 正视相机(沿 +Y 看)下, 法线朝后(+Y) = 用户叠加显示里的红
for p in me.polygons:
    p.material_index = 1 if p.normal.y > 0.05 else 0

tgt = Vector((cx, cy, cz))
cnt = [0] * 4
red = [0] * 4
red_area = 0.0
zero_area = 0
edges = (0.0015, 0.003, 0.008, 0.020)
for p in me.polygons:
    c = p.center
    if c.y > -0.02:          # 只排后脑(眼周皮肤在 -0.09~-0.13, 比眼中心还靠后)
        continue
    d = math.hypot(c.x - cx, c.z - cz)
    for i, e in enumerate(edges):
        if (i == 0 and d < e) or (i > 0 and edges[i - 1] <= d < e):
            cnt[i] += 1
            if p.normal.y > 0.05:
                red[i] += 1
                if p.area < 1e-12:
                    zero_area += 1
                else:
                    red_area += p.area
            break
labels = ("<1.5mm", "1.5~3mm", "3~8mm", "8~20mm")
for i, lb in enumerate(labels):
    print(f"  {lb} from center: red {red[i]}/{cnt[i]}")
print(f"  红面实体总面积 {red_area * 1e6:.4f}mm^2 (其中 0 面积退化面 {zero_area} 个, 渲染不可见)")

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'FLAT'
scn.display.shading.color_type = 'MATERIAL'
cam = bpy.data.objects.get("_focam") or bpy.data.objects.new("_focam", bpy.data.cameras.new("_focam"))
try:
    scn.collection.objects.link(cam)
except Exception:
    pass
scn.camera = cam
cam.data.type = 'ORTHO'


def shoot(name, ax, az, sc_=0.05):
    scn.render.resolution_x = 1000
    scn.render.resolution_y = 760
    cam.data.ortho_scale = sc_
    cam.location = (tgt.x + math.sin(az) * 0.25,
                    tgt.y - math.cos(az) * math.cos(ax) * 0.25,
                    tgt.z + math.sin(ax) * 0.25)
    d = tgt - Vector(cam.location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scn.render.filepath = os.path.join(outdir, name)
    bpy.ops.render.render(write_still=True)


shoot("fo_front.png", 0.0, 0.0)
shoot("fo_low.png", -0.30, -0.25)
print(f"渲染完成 -> {outdir}/fo_front.png, fo_low.png (蓝=正面, 红=反面)")
