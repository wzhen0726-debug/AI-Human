"""ARP方案绑定 — 利用Auto-Rig Pro Smart后台模式自动生成骨骼+权重
模型身高1.80m, 与ARP模板(~1.8m)匹配, 不需要缩放.
用法: blender -b --python arp_rig.py
"""
import bpy, sys, os

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
BODY = os.path.join(DELIVERY, "04纹理烘焙", "04_bake.blend")
OUT_BLEND = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp.blend")
OUT_GLB = os.path.join(DELIVERY, "05骨骼绑定", "B_骨骼绑定", "06_rig_arp.glb")
# AI根目录: ARP会自动追加inference\子目录, 所以不能以inference结尾
# (错误路径 ...\AI\inference 会变成 ...\AI\inference\inference\front1_kp.py)
AI_PATH = r"C:\Users\Liyunzhong\Documents\AutoRigPro\AI"

print("\n=== ARP绑定开始 ===")

# 1. 先清场景(必须在enable之前, 否则reset会卸载插件)
bpy.ops.wm.read_factory_settings(use_empty=True)

# 2. 启用ARP插件
res = bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
print(f"启用ARP: {res}")

# 3. 设置AI路径(必须在插件注册后)
arp_key = 'auto_rig_pro-master'
if arp_key in bpy.context.preferences.addons:
    bpy.context.preferences.addons[arp_key].preferences.ai_presets_path = AI_PATH
    print(f"AI路径已设置: {AI_PATH}")
else:
    print(f"WARNING: 插件名{arp_key}未注册, 尝试查找...")
    for k in bpy.context.preferences.addons.keys():
        if 'auto_rig' in k:
            print(f"  找到: {k}")
            bpy.context.preferences.addons[k].preferences.ai_presets_path = AI_PATH
            break

# 4. 补丁: 后台模式popup崩溃
ara = None
for key, mod in sys.modules.items():
    if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
        ara = mod
        break
if ara:
    def popup_patched(message, header=' ', icon_type=''):
        print(f"[ARP {header}] {message}")
    ara.display_popup_message = popup_patched
    print("popup补丁OK")

# 3. 补丁: OpenGL渲染→Cycles
ars = None
for key, mod in sys.modules.items():
    if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
        ars = mod
        break

def screenshot_patched(self):
    """完全复刻ARP原生_screenshot_char的相机逻辑, 但用Cycles渲染(后台无OpenGL).
    关键: 文件名必须是 front1.jpg / char_side.jpg / char_top.jpg (推理exe固定读这些名)."""
    import math
    from mathutils import Vector
    scn = bpy.context.scene
    orig_engine = scn.render.engine
    orig_x, orig_y = scn.render.resolution_x, scn.render.resolution_y

    scn.render.engine = 'BLENDER_EEVEE'
    scn.render.resolution_x = 512
    scn.render.resolution_y = 512
    # 关键: 推理exe只读.jpg, 必须强制JPEG格式(否则按场景设置存成.png, exe找不到文件)
    scn.render.image_settings.file_format = 'JPEG'

    body_temp = bpy.data.objects.get('body_temp')
    if not body_temp:
        print("ERROR: body_temp not found")
        return

    # 灰色材质 + 暗背景 (AI模型训练条件: 0.8灰模型 + 0.04暗背景)
    # 关键: 用Emission自发光, 不依赖场景灯光(后台无灯光时BSDF渲染成黑色剪影, AI识别不出人体)
    mat = bpy.data.materials.new("arp_gray")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes["Principled BSDF"].inputs["Base Color"].default_value = (0, 0, 0, 1.0)
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    mat.node_tree.links.new(emit.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    body_temp.data.materials.clear()
    body_temp.data.materials.append(mat)
    # 截图函数需维护此列表, ARP后续_set_markers_from_keypoints会读取
    self.front_samples_rot = [0.0]

    if scn.world is None:
        scn.world = bpy.data.worlds.new("arp_bg")
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
    bg.inputs["Strength"].default_value = 1.0

    # 相机(复刻原生: bbox + ortho)
    bbox_corners = [body_temp.matrix_world @ Vector(corner) for corner in body_temp.bound_box]
    x1, x2 = bbox_corners[0][0], bbox_corners[4][0]
    y1, y2 = bbox_corners[0][1], bbox_corners[6][1]
    z1, z2 = bbox_corners[0][2], bbox_corners[2][2]
    dim_x, dim_y, dim_z = abs(x2-x1), abs(y2-y1), abs(z2-z1)
    midx = (x1+x2)*0.5
    midy = (y1+y2)*0.5
    midz = (z1+z2)*0.5
    lower_y = min(y1, y2)
    greater_x = max(x1, x2)
    greater_z = max(z1, z2)
    larger_dim = max(dim_x, dim_z)
    larger_dimy = max(dim_y, dim_z)
    larger_dimtop = max(dim_y, dim_x)
    margin = self.margin if hasattr(self, 'margin') else 1.2

    cam_data = bpy.data.cameras.new("arp_cam_char")
    cam_data.type = 'ORTHO'
    cam_data.clip_end = 50000
    cam_obj = bpy.data.objects.new("arp_cam_char", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    scn.camera = cam_obj

    inf = self.inf_path
    def render_view(name, loc, rot, ortho):
        cam_obj.location = loc
        cam_obj.rotation_euler = rot
        cam_obj.data.ortho_scale = ortho
        scn.render.filepath = os.path.join(inf, name)
        bpy.ops.render.render(write_still=True)
        print(f"  截图: {name}")

    # front1: 从-Y方向看(正面), 正交
    render_view("front1.jpg",
                (midx, lower_y - dim_y*10, midz),
                (math.pi/2, 0, 0),
                larger_dim * margin)
    # char_side: 从+X方向看(侧面)
    render_view("char_side.jpg",
                (greater_x + dim_x*10, midy, midz),
                (math.pi/2, 0, math.pi/2),
                larger_dimy * margin)
    # char_top: 从+Z向下看(俯视)
    render_view("char_top.jpg",
                (midx, midy, greater_z + dim_z*10),
                (0, 0, 0),
                larger_dimtop * margin)

    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    scn.render.engine = orig_engine
    scn.render.resolution_x, scn.render.resolution_y = orig_x, orig_y

if ars:
    ars._screenshot_char = screenshot_patched
    print("截图补丁OK")
else:
    print("WARNING: auto_rig_smart模块未找到, 截图补丁跳过")

# 4. 打开模型(用append方式, 避免open_mainfile重置插件状态)
with bpy.data.libraries.load(BODY, link=False) as (d_from, d_to):
    d_to.objects = [n for n in d_from.objects]
for o in d_to.objects:
    if o:
        bpy.context.scene.collection.objects.link(o)

# 找主体
cands = [o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()]
body = max(cands, key=lambda o: len(o.data.polygons))
print(f"身体: {body.name}, {len(body.data.vertices)}顶点")

# 选中
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body

# 5. 获取VIEW_3D上下文
bpy.context.window.screen = bpy.data.screens['Layout']
area = None
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        area = a
        break
region = None
for r in area.regions:
    if r.type == 'WINDOW':
        region = r
        break
print(f"上下文: area={'OK' if area else 'FAIL'}, region={'OK' if region else 'FAIL'}")

# 6. AI路径已在开头设置(第3步)

# 7. 执行ARP Smart三步
with bpy.context.temp_override(area=area, region=region):
    print("\n--- Step 1: get_selected_objects ---")
    bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
    
    print("\n--- Step 2: guess_markers ---")
    # 只取1张正面样本(我的截图补丁只渲染front1.jpg, 默认2张会找front2报错)
    bpy.context.scene.arp_smart_AI_body_samples = 1
    try:
        bpy.ops.arp.guess_markers('EXEC_DEFAULT')
        print("guess_markers 完整成功")
    except Exception as e:
        # guess_markers可能在臂角计算处崩溃(shoulder==hand零向量),
        # 但截图+推理+标记对象创建通常已完成, 继续用几何修正覆盖标记位置
        print(f"guess_markers 部分完成后异常(可忽略, 几何修正会覆盖): {type(e).__name__}")
    
    # 检查标记
    markers = [o for o in bpy.data.objects if o.name.endswith('_loc') or o.name.endswith('_loc_sym')]
    print(f"AI标记: {len(markers)}个")
    for m in markers[:5]:
        print(f"  {m.name}: ({m.location.x:.3f}, {m.location.y:.3f}, {m.location.z:.3f})")
    
    # 8. 用几何修正标记位置(防止AI边缘检测失败)
    scn = bpy.context.scene
    verts = body.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    H = max_z - min_z
    midx = (min_x + max_x) / 2
    midy = (min_y + max_y) / 2
    
    def clamp(v, lo, hi, m=0.02):
        return max(lo+m, min(hi-m, v))
    
    def fix(name, x, y, z):
        o = bpy.data.objects.get(name)
        if o:
            o.location = (clamp(x,min_x,max_x), clamp(y,min_y,max_y), clamp(z,min_z,max_z))
    
    # 身高分布测量(与measure_joints相同方法)
    import numpy as np
    hp = np.array([[v.co.x, v.co.y, v.co.z] for v in verts])
    
    def band(zlo, zhi, xf=None):
        m = (hp[:,2]>=zlo)&(hp[:,2]<=zhi)
        if xf: m &= xf(hp[:,0])
        return hp[m]
    
    # 手臂带
    arm_zc = None
    for frac in np.arange(0.82, 0.74, -0.005):
        b = band(min_z+H*frac, min_z+H*(frac+0.01))
        if len(b) > 50:
            span = b[:,0].max()-b[:,0].min()
            if span > 0.6:
                arm_zc = min_z + H*(frac+0.005)
                break
    
    if arm_zc:
        arm_band = band(arm_zc-H*0.02, arm_zc+H*0.02)
        arm_center_y = float(arm_band[arm_band[:,0]>0.35][:,1].mean()) if len(arm_band[arm_band[:,0]>0.35])>0 else midy
        hand_tip = float(arm_band[:,0].max())
        
        # 肩(手臂带内侧)
        inner = arm_band[arm_band[:,0] > 0.10]
        shoulder_x = float(np.percentile(inner[:,0], 10)) if len(inner)>10 else 0.18
        
        # 肘/腕(厚度剖面)
        def thickness(x):
            sl = hp[(np.abs(hp[:,0]-x)<0.008)&(hp[:,2]>arm_zc-H*0.04)&(hp[:,2]<arm_zc+H*0.04)]
            if len(sl)<10: return 999
            return sl[:,1].max()-sl[:,1].min()
        prof = [(x, thickness(x)) for x in np.arange(0.25, hand_tip-0.03, 0.01)]
        ts = [t for _,t in prof]
        if ts:
            tmin = min(ts)
            tmax = max(ts)
            thresh = tmin + (tmax-tmin)*0.35
            elbow_x = wrist_x = None
            for x, t in prof:
                if elbow_x is None and t < thresh:
                    elbow_x = x
                if elbow_x and t > thresh:
                    wrist_x = x
                    break
            if elbow_x is None: elbow_x = 0.45
            if wrist_x is None: wrist_x = 0.65
        else:
            elbow_x, wrist_x = 0.45, 0.65
        
        # 修正标记
        z_sh = arm_zc
        fix('shoulder_loc', shoulder_x, arm_center_y, z_sh)
        fix('shoulder_loc_sym', -shoulder_x, arm_center_y, z_sh)
        fix('hand_loc', wrist_x, arm_center_y, z_sh)
        fix('hand_loc_sym', -wrist_x, arm_center_y, z_sh)
        fix('elbow_loc', elbow_x, arm_center_y, z_sh)
        fix('elbow_loc_sym', -elbow_x, arm_center_y, z_sh)
        print(f"几何修正: 肩x={shoulder_x:.3f} 肘x={elbow_x:.3f} 腕x={wrist_x:.3f} 臂z={arm_zc:.3f}")
    
    # 腿(左右)
    for side, sign in [('R', 1), ('L', -1)]:
        leg_x = None
        for zf in np.arange(0.30, 0.05, -0.01):
            b = band(min_z+H*zf, min_z+H*(zf+0.02))
            if len(b)<20: continue
            xr = b[b[:,0]*sign > 0.03]
            xl = b[b[:,0]*sign < -0.03]
            if len(xr)>20 and len(xl)>20:
                leg_x = abs(float(xr[:,0].mean()))
                break
        if leg_x:
            knee_z = min_z + H*0.25
            ankle_z = min_z + H*0.07
            foot_z = min_z + H*0.02
            fix(f'knee_loc' if side=='R' else 'knee_loc_sym', sign*leg_x, midy, knee_z)
            fix(f'foot_loc' if side=='R' else 'foot_loc_sym', sign*leg_x, midy, foot_z)
            fix(f'thigh_loc' if side=='R' else 'thigh_loc_sym', sign*leg_x, midy, min_z+H*0.40)
    
    # 根/颈/下巴
    fix('root_loc', midx, midy, min_z + H*0.53)
    fix('neck_loc', midx, midy, min_z + H*0.87)
    fix('chin_loc', midx, min_y + 0.02, min_z + H*0.85)
    
    # 9. 关闭深度检测(用标记Y位置代替射线)
    scn.arp_smart_depth = False
    
    print("\n--- Step 3: go_detect ---")
    try:
        bpy.ops.id.go_detect('EXEC_DEFAULT')
        print("go_detect成功")
    except Exception as e:
        print(f"go_detect异常: {e}")
        # 继续尝试权重绑定

# 10. 检查骨架
arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
        break

if arm:
    print(f"\n骨架: {arm.name}, {len(arm.data.bones)}根骨骼", flush=True)

    # 10b. 先保存骨架状态(即使权重失败也有中间产物)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
        print(f"中间保存: {OUT_BLEND}", flush=True)
    except Exception as e:
        print(f"中间保存失败: {e}", flush=True)

    # 11. 权重绑定 (后台模式: select_all等operator的poll失败, 用纯Python操作)
    try:
        for o in bpy.data.objects:
            o.select_set(False)
        body.select_set(True)
        arm.select_set(True)
        # parent_set需要window/screen上下文
        win = bpy.context.window
        screen = bpy.context.screen or bpy.data.screens[0]
        with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print(f"权重绑定: {len(body.vertex_groups)}个顶点组", flush=True)
    except Exception as e:
        print(f"parent_set失败({type(e).__name__}), 用armature修改器兜底: {e}", flush=True)
        # 兜底: Python API直接parent+armature修改器(无自动权重, 但结构完整)
        body.parent = arm
        existing = [m for m in body.modifiers if m.type == 'ARMATURE']
        if not existing:
            mod = body.modifiers.new('Armature', 'ARMATURE')
            mod.object = arm
        print("已用armature修改器兜底(无自动权重, 需后续补)", flush=True)

    # 12. 保存最终
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"保存: {OUT_BLEND}", flush=True)

    # 13. 导出GLB
    try:
        bpy.ops.export_scene.gltf(
            filepath=OUT_GLB,
            export_format='GLB',
            use_selection=False,
        )
        print(f"GLB: {OUT_GLB}", flush=True)
    except Exception as e:
        print(f"GLB导出失败: {type(e).__name__}: {e}", flush=True)
else:
    print("ERROR: 未生成骨架")

print("\nARP_RIG_DONE")
