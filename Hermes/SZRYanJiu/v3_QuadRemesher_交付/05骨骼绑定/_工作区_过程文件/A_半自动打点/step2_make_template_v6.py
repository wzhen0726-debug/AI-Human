"""第2步: 生成ARP打点模板v6 — 完全照抄手动版点的规格.
手动版实测规格(01_打点模板.blend): Empty SPHERE空心小球, size=0.012, show_in_front=True,
视口Material+ORTHO. 之前我一直做mesh实心球, 所以用户说"奇怪".
点位用第1步AI实测位置, 官方命名(root_loc/chin_loc/...), _sym镜像驱动跟随."""
import bpy, os, json, math
from mathutils import Quaternion

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定"
BAKE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\04纹理烘焙\04_bake.blend"
PTS = os.path.join(BASE, "_工作区_过程文件", "logs", "ai_points.json")
OUT = os.path.join(BASE, "_工作区_过程文件", "A_半自动打点", "08_arp打点模板_v6.blend")

pts = json.load(open(PTS, encoding="utf-8"))
print(f"AI点位读入: {len(pts)}")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BAKE)

# 删掉非mesh对象(相机/灯等), 保留身体
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)
print(f"保留mesh对象: {[o.name for o in bpy.data.objects]}")

# ===== Empty SPHERE标记 (照抄手动版规格) =====
SIZE = 0.012   # 手动版实测值
colors = {}
for name, p in pts.items():
    if name.endswith('_sym'):
        colors[name] = (0.25, 0.5, 1.0, 1.0)      # 蓝=镜像侧
    elif name in ('root_loc', 'chin_loc', 'neck_loc'):
        colors[name] = (1.0, 0.8, 0.0, 1.0)        # 黄=中线
    elif name in ('thigh_loc', 'knee_loc', 'foot_loc'):
        colors[name] = (0.2, 0.9, 0.2, 1.0)        # 绿=腿
    else:
        colors[name] = (1.0, 0.25, 0.1, 1.0)       # 红=臂

for name, p in pts.items():
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = 'SPHERE'      # 手动版同款: 空心线框球
    o.empty_display_size = SIZE
    o.location = p
    o.show_in_front = True               # 身体内的点也永远可见
    o.color = colors[name]               # Blender4.2+ 对象视口颜色(作用于Empty线框)
    o["arp_marker"] = 1
    bpy.context.scene.collection.objects.link(o)

# 中线点表面吸附(手动版同款: 头顶/颈根/会阴有Shrinkwrap) — ARP版只有chin是明确表面点
body = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
chin = bpy.data.objects.get('chin_loc')
if chin:
    sw = chin.constraints.new('SHRINKWRAP')
    sw.target = body
    sw.shrinkwrap_type = 'NEAREST_SURFACE'   # Blender5.1枚举: NEAREST_SURFACE/PROJECT/NEAREST_VERTEX/TARGET_PROJECT
    ll = chin.constraints.new('LIMIT_LOCATION')
    ll.use_min_x = ll.use_max_x = ll.use_min_y = ll.use_max_y = ll.use_min_z = ll.use_max_z = True
    n_v = len(body.data.vertices)
    bx = [body.matrix_world @ body.data.vertices[i].co for i in range(0, n_v, 50)]
    ll.min_x, ll.max_x = min(v.x for v in bx) - 0.05, max(v.x for v in bx) + 0.05
    ll.min_y, ll.max_y = min(v.y for v in bx) - 0.05, max(v.y for v in bx) + 0.05
    ll.min_z, ll.max_z = min(v.z for v in bx) - 0.05, max(v.z for v in bx) + 0.05
    print("chin_loc 加Shrinkwrap+LIMIT_LOCATION")

# ===== 镜像驱动: _sym跟随主点 (手动版同款机制) =====
n_drv = 0
for name in pts:
    if not name.endswith('_sym'):
        continue
    main_name = name[:-4]
    main, sym = bpy.data.objects.get(main_name), bpy.data.objects.get(name)
    if not main or not sym:
        continue
    for ax in range(3):
        fcurve = sym.driver_add("location", ax)
        drv = fcurve.driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = "m"
        var.type = 'TRANSFORMS'
        var.targets[0].id = main
        var.targets[0].transform_type = ['LOC_X', 'LOC_Y', 'LOC_Z'][ax]
        var.targets[0].transform_space = 'WORLD_SPACE'
        drv.expression = "-m" if ax == 0 else "m"
        n_drv += 1
    sym.hide_select = True   # 镜像点禁止误选
    sym.select_set(False)
    sym["arp_mirror_of"] = main_name
print(f"镜像驱动: {n_drv}条")

# ===== 说明牌(简短) =====
def make_text(txt, loc, size):
    cu = bpy.data.curves.new("tip", 'FONT')
    cu.body = txt
    cu.size = size
    cu.align_x = 'LEFT'
    o = bpy.data.objects.new("说明", cu)
    o.location = loc
    o.rotation_euler = (math.pi/2, 0, 0)   # 面向前视相机
    o.show_in_front = True
    o.color = (1, 1, 1, 1)
    bpy.context.scene.collection.objects.link(o)
    return o

make_text("ARP打点模板 — 只调右侧(红/绿/黄)点, 左侧蓝点自动镜像跟随", (-1.75, -1.2, 1.72), 0.045)
make_text("调完 Ctrl+S 保存即可. 黄=中线 红=手臂 绿=腿 蓝=自动镜像", (-1.75, -1.2, 1.62), 0.035)

# ===== 视口: Material + 正面正交(照抄手动版) =====
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type != 'VIEW_3D':
            continue
        for sp in area.spaces:
            if sp.type != 'VIEW_3D':
                continue
            sp.shading.type = 'MATERIAL'
            sp.shading.light = 'STUDIO'
            sp.shading.color_type = 'MATERIAL'
            sp.overlay.show_text = True
            if sp.region_3d:
                sp.region_3d.view_perspective = 'ORTHO'
                sp.region_3d.view_rotation = Quaternion((0.7071, 0.7071, 0, 0))  # 正视
                sp.region_3d.view_location = (0, 0, 0.9)
                sp.region_3d.view_distance = 2.2
print("视口配置完成")

bpy.ops.wm.save_mainfile(filepath=OUT)
print(f"保存: {OUT}")
print("TEMPLATE_V6_DONE")
