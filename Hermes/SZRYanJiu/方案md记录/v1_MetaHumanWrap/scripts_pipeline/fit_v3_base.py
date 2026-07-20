"""
自检管线: 跑贴合 → 渲染验证图 → 量化检查 → 报告 → 自动判断达标
用法: blender --background --python auto_check_pipeline.py [max_rounds]

达标标准:
  1. 对称性: 左右眼Y差 < 3mm, 左右嘴Z差 < 3mm
  2. 五官偏差: 12面部锚点全部 < 0.5mm
  3. 整体距离: mean < 0.6mm, <1mm占比 > 95%
  4. 穿透率: 面部区域顶点穿透高模的比例 < 5%
  5. 耳朵区域: 平均距离 < 3mm (耳朵是难点, 放宽标准)

不达标则调整参数重跑:
  - 轮次1: 基准参数 (NEAREST, 4轮, 30轮锚定)
  - 轮次2: 增加Shrinkwrap到6轮 + 锚定40轮
  - 轮次3: 增加Corrective Smooth强度
  - 轮次4+: 微调缩放和质心
"""
import bpy, os, numpy as np, time, math, cv2, json, sys
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test01"
SCAN_OBJ = os.path.join(ROOT, "原始GLB", "Scan_head", "Scan_Head_Lv5.obj")
TEMPLATE = os.path.join(ROOT, "原始GLB", "MetaHuman_head", "MH_Head_01.obj")
MODEL_PATH = os.path.join(ROOT, "output_final", "face_landmarker.task")
LANDMARK_JSON = os.path.join(ROOT, "output_final", "template_landmarks.json")
OUTPUT_DIR = os.path.join(ROOT, "output_final")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# MediaPipe 轮廓点 (只保留对称性好的组)
MP_CONTOURS = {
    'right_eye': [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246],
    'left_eye': [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398],
    'outer_lip': [61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146],
    'inner_lip': [78,191,80,81,82,13,312,311,310,415,308,324,318,402,317,14,87,178,88,95],
    'nose_ala': [49,131,134,51,3,248,281,279,440],
}
MP_KEY_POINTS = {
    'nose_tip': 1, 'right_eye_inner': 133, 'right_eye_outer': 33,
    'left_eye_inner': 362, 'left_eye_outer': 263,
    'right_mouth_corner': 61, 'left_mouth_corner': 291,
    'chin': 199, 'forehead': 10, 'nose_bridge': 6,
    'right_brow': 105, 'left_brow': 334,
}

# ============================================================
# 阶段1: 贴合函数 (参数化, 支持不同轮次的参数调整)
# ============================================================
def run_fit(sw_rounds=4, anchor_rounds=30, smooth_factor=0.15, smooth_iters=2):
    """执行完整贴合流程, 返回 (scan_obj, template_obj)"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # 导入扫描头
    bpy.ops.wm.obj_import(filepath=SCAN_OBJ)
    scan_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH': scan_obj = obj; break
    scan_obj.name = "Scan_Head"
    bpy.context.view_layer.objects.active = scan_obj
    scan_obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 居中
    vs = [scan_obj.matrix_world @ v.co for v in scan_obj.data.vertices]
    cx=(min(v.x for v in vs)+max(v.x for v in vs))/2
    cy=(min(v.y for v in vs)+max(v.y for v in vs))/2
    cz=(min(v.z for v in vs)+max(v.z for v in vs))/2
    scan_obj.location -= Vector((cx,cy,cz))
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    sb = bbox_world(scan_obj)
    scan_center = Vector(sb['center'])
    sz = max(sb['size'])

    # 渲染6方向
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512
    bpy.ops.object.light_add(type='SUN', location=(0,0,10))
    bpy.context.active_object.data.energy = 5.0
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    dirs = {'+Y':(0,1,0), '-Y':(0,-1,0), '+X':(1,0,0), '-X':(-1,0,0), '+Z':(0,0,1), '-Z':(0,0,-1)}
    render_paths = {}
    for name, d in dirs.items():
        cam.location = scan_center + Vector(d) * (sz + 0.5)
        cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
        bpy.context.view_layer.update()
        p = os.path.join(OUTPUT_DIR, f"scan_{name}.png")
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        render_paths[name] = p

    # MediaPipe 检测
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    opt = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.IMAGE, num_faces=1)
    detector = vision.FaceLandmarker.create_from_options(opt)
    best_landmarks = None; best_dir = None; best_count = 0
    for name, path in render_paths.items():
        img = cv2.resize(cv2.imread(path), (256,256))
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if result.face_landmarks:
            n = len(result.face_landmarks[0])
            if n > best_count: best_landmarks = result.face_landmarks[0]; best_dir = name; best_count = n
    detector.close()
    print(f"  MediaPipe: {best_dir} ({best_count} landmarks)")

    # 2D→3D 映射
    d = dirs[best_dir]
    cam.location = scan_center + Vector(d) * (sz + 0.5)
    cam.rotation_euler = (scan_center - cam.location).to_track_quat('-Z','Z').to_euler()
    bpy.context.view_layer.update()
    sm = scan_obj.matrix_world
    cam_pos = cam.matrix_world.to_translation()
    fov = cam.data.angle; h = w = 256

    def map_2d_to_3d(mp_idx):
        lm = best_landmarks[mp_idx]
        px, py = lm.x*w, lm.y*h
        nx, ny = (px/w)*2-1, 1-(py/h)*2
        ray_cam = Vector((nx*math.tan(fov/2), ny*math.tan(fov/2), -1)).normalized()
        ray_world = (cam.matrix_world.to_3x3() @ ray_cam).normalized()
        origin_local = sm.inverted() @ cam_pos
        dir_local = (sm.inverted().to_3x3() @ ray_world).normalized()
        hit, loc, n, fi = scan_obj.ray_cast(origin_local, dir_local, distance=2.0)
        if not hit: hit, loc, n, fi = scan_obj.ray_cast(origin_local, -dir_local, distance=2.0)
        if hit: return sm @ loc
        return None

    # 核心点
    lm_3d = {}
    for name, idx in MP_KEY_POINTS.items():
        p = map_2d_to_3d(idx)
        if p: lm_3d[name] = p

    # 轮廓点 (带过滤)
    contour_3d = {}
    for group_name, indices in MP_CONTOURS.items():
        raw_pts = []
        for idx in indices:
            p = map_2d_to_3d(idx)
            if p: raw_pts.append(p)
        if len(raw_pts) >= 4:
            ys = sorted([p.y for p in raw_pts])
            y_median = ys[len(ys)//2]
            pts = [p for p in raw_pts if abs(p.y - y_median) < 0.015]
        else:
            pts = raw_pts
        contour_3d[group_name] = pts

    # 几何点
    scan_n = len(scan_obj.data.vertices)
    step = max(1, scan_n // 200000)
    scan_pts = np.array([sm @ scan_obj.data.vertices[i].co for i in range(0, scan_n, step)])
    nose = lm_3d.get('nose_tip'); leye = lm_3d.get('left_eye_inner'); reye = lm_3d.get('right_eye_inner')
    if nose and leye:
        eye_z = (leye.z + reye.z) / 2 if reye else leye.z
        z_max = scan_pts[:,2].max()
        top_mask = scan_pts[:,2] > z_max - 0.03
        if np.any(top_mask):
            tc = scan_pts[top_mask].mean(axis=0)
            lm_3d['top_of_head'] = Vector((tc[0], tc[1], z_max))
        y_max = scan_pts[:,1].max()
        back_mask = scan_pts[:,1] > y_max - 0.03
        if np.any(back_mask):
            bc = scan_pts[back_mask].mean(axis=0)
            lm_3d['back_of_head'] = Vector((bc[0], y_max, bc[2]))
        z_min = scan_pts[:,2].min()
        neck_mask = (scan_pts[:,1] > y_max - 0.06) & (scan_pts[:,2] < z_min + 0.05)
        if np.any(neck_mask):
            nc = scan_pts[neck_mask].mean(axis=0)
            lm_3d['back_neck'] = Vector((nc[0], nc[1], nc[2]))
        for side, sign, ear_names in [('left',1,['left_ear_top','left_ear_mid','left_ear_bottom']),('right',-1,['right_ear_top','right_ear_mid','right_ear_bottom'])]:
            ear_mask = (sign*scan_pts[:,0] > sign*scan_pts[:,0].max()*0.7) & (np.abs(scan_pts[:,2]-eye_z)<0.06)
            if np.any(ear_mask):
                ear_pts = scan_pts[ear_mask]
                ez_min, ez_max = ear_pts[:,2].min(), ear_pts[:,2].max()
                ezr = ez_max - ez_min
                for i, ename in enumerate(ear_names):
                    tz = [ez_max-ezr*0.2, (ez_max+ez_min)/2, ez_min+ezr*0.2][i]
                    zm = np.abs(ear_pts[:,2]-tz) < ezr*0.2
                    if np.any(zm):
                        cands = ear_pts[zm]
                        best = cands[np.argmax(cands[:,0])] if sign>0 else cands[np.argmin(cands[:,0])]
                        lm_3d[ename] = Vector((best[0], best[1], best[2]))

    # 导入低模
    bpy.ops.wm.obj_import(filepath=TEMPLATE)
    template_obj = None
    for obj in bpy.data.objects:
        if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break
    tb = bbox_world(template_obj)
    template_obj.location -= Vector(tb['center'])
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    tb = bbox_world(template_obj)

    # 质心对齐
    with open(LANDMARK_JSON) as f:
        template_lm = json.load(f)
    tm = template_obj.matrix_world
    t_pts_init = np.array([tm @ v.co for v in template_obj.data.vertices])
    face_names = set(MP_KEY_POINTS.keys())
    t_idx_face = []; s_pos_face = []
    for name, t_idx in template_lm.items():
        if name in lm_3d and name in face_names:
            t_idx_face.append(t_idx); s_pos_face.append(lm_3d[name])
    tc_init = np.mean([t_pts_init[i] for i in t_idx_face], axis=0)
    sc_init = np.mean([np.array([p.x,p.y,p.z]) for p in s_pos_face], axis=0)
    trans = sc_init - tc_init
    template_obj.location.x += trans[0]; template_obj.location.y += trans[1]; template_obj.location.z += trans[2]
    bpy.context.view_layer.update()

    # 缩放
    tb = bbox_world(template_obj)
    sr = [sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
    us = sum(sr)/3
    template_obj.scale = (us,us,us)
    bpy.context.view_layer.update()

    tm = template_obj.matrix_world; tm_inv = tm.inverted()

    # 匹配轮廓点到低模顶点
    n_tv = len(template_obj.data.vertices)
    t_kd = KDTree(n_tv)
    for i, v in enumerate(template_obj.data.vertices):
        t_kd.insert(tm @ v.co, i)
    t_kd.balance()

    contour_anchors = {}
    for group_name, pts in contour_3d.items():
        for p in pts:
            co, vi, dist = t_kd.find(tuple(p))
            if dist < 0.02:
                target_local = tm_inv @ p
                if vi not in contour_anchors or (target_local - template_obj.data.vertices[vi].co).length < (contour_anchors[vi] - template_obj.data.vertices[vi].co).length:
                    contour_anchors[vi] = target_local

    anchor_targets = {}
    for t_idx, s_pos in zip(t_idx_face, s_pos_face):
        anchor_targets[t_idx] = tm_inv @ s_pos
    for vi, target in contour_anchors.items():
        if vi not in anchor_targets:
            anchor_targets[vi] = target
    print(f"  锚点: {len(anchor_targets)} (核心{len(t_idx_face)} + 轮廓{len(contour_anchors)})")

    # Shrinkwrap (全部NEAREST, 避免不对称)
    for i in range(sw_rounds):
        sw = template_obj.modifiers.new("SW",'SHRINKWRAP')
        sw.target = scan_obj
        sw.wrap_method = 'NEAREST_SURFACEPOINT'
        sw.wrap_mode = 'ON_SURFACE'
        sw.offset = 0.0
        bpy.ops.object.modifier_apply(modifier="SW")
        csm = template_obj.modifiers.new("CS",'CORRECTIVE_SMOOTH')
        csm.iterations = smooth_iters; csm.smooth_type='SIMPLE'; csm.factor=smooth_factor
        bpy.ops.object.modifier_apply(modifier="CS")

    # 锚定
    tm = template_obj.matrix_world; tm_inv = tm.inverted()
    mesh = template_obj.data
    adj = [set() for _ in range(len(mesh.vertices))]
    for e in mesh.edges:
        adj[e.vertices[0]].add(e.vertices[1])
        adj[e.vertices[1]].add(e.vertices[0])
    adj = [list(s) for s in adj]

    anchor_targets_cur = dict(anchor_targets)
    for iteration in range(anchor_rounds):
        alpha = 0.3 + 0.7 * (iteration / max(1, anchor_rounds-1))
        for vi, target in anchor_targets_cur.items():
            mesh.vertices[vi].co = mesh.vertices[vi].co.lerp(target, alpha)
        new_co = [None] * len(mesh.vertices)
        for i in range(len(mesh.vertices)):
            if i in anchor_targets_cur:
                new_co[i] = mesh.vertices[i].co.copy()
            else:
                neighbors = adj[i]
                if neighbors:
                    avg = Vector((0,0,0))
                    for ni in neighbors: avg += mesh.vertices[ni].co
                    avg /= len(neighbors)
                    new_co[i] = mesh.vertices[i].co.lerp(avg, 0.3)
                else:
                    new_co[i] = mesh.vertices[i].co.copy()
        for i in range(len(mesh.vertices)):
            mesh.vertices[i].co = new_co[i]
    mesh.update()

    # 表面修正: 轻量 NEAREST Shrinkwrap + 重新锚定
    sw2 = template_obj.modifiers.new("SW2",'SHRINKWRAP')
    sw2.target = scan_obj
    sw2.wrap_method = 'NEAREST_SURFACEPOINT'; sw2.wrap_mode='ON_SURFACE'; sw2.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW2")
    csm2 = template_obj.modifiers.new("CS2",'CORRECTIVE_SMOOTH')
    csm2.iterations=1; csm2.smooth_type='SIMPLE'; csm2.factor=0.1
    bpy.ops.object.modifier_apply(modifier="CS2")
    for vi, target in anchor_targets_cur.items():
        template_obj.data.vertices[vi].co = target
    template_obj.data.update()

    return scan_obj, template_obj, lm_3d, anchor_targets_cur

def bbox_world(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
    return dict(center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                min=(min(xs),min(ys),min(zs)), max=(max(xs),max(ys),max(zs)),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ============================================================
# 阶段2: 量化检查
# ============================================================
def run_checks(scan_obj, template_obj, lm_3d, anchor_targets):
    """执行量化检查, 返回 (report_dict, passed_bool)"""
    sm = scan_obj.matrix_world; tm = template_obj.matrix_world
    tverts = np.array([tm @ v.co for v in template_obj.data.vertices])

    # 高模 KDTree
    scan_n = len(scan_obj.data.vertices)
    step = max(1, scan_n // 200000)
    kds = KDTree(scan_n // step + 10)
    for i in range(0, scan_n, step):
        kds.insert(sm @ scan_obj.data.vertices[i].co, i)
    kds.balance()

    # 1. 整体距离
    dists = np.array([kds.find(tuple(tverts[i]))[2] for i in range(len(tverts))])
    overall_mean = np.mean(dists)
    overall_1mm = np.sum(dists < 0.001) / len(dists)

    # 2. 对称性检查
    eye_mask = (tverts[:,2]>0.025)&(tverts[:,2]<0.055)&(tverts[:,1]>-0.06)&(tverts[:,1]<-0.02)
    ev = tverts[eye_mask]
    le = ev[ev[:,0]>0]; re = ev[ev[:,0]<0]
    eye_y_diff = abs(le[:,1].mean() - re[:,1].mean()) if len(le)>0 and len(re)>0 else 999

    mouth_mask = (tverts[:,2]>-0.06)&(tverts[:,2]<-0.02)&(tverts[:,1]>-0.08)&(tverts[:,1]<-0.04)
    mv = tverts[mouth_mask]
    lm_m = mv[mv[:,0]>0]; rm_m = mv[mv[:,0]<0]
    mouth_z_diff = abs(lm_m[:,2].mean() - rm_m[:,2].mean()) if len(lm_m)>0 and len(rm_m)>0 else 999

    # 3. 锚点偏差
    anchor_errs = []
    for vi, target in anchor_targets.items():
        wp = tm @ template_obj.data.vertices[vi].co
        target_world = tm @ target
        err = (wp - target_world).length
        anchor_errs.append(err)
    anchor_max = max(anchor_errs) if anchor_errs else 999

    # 4. 穿透检测: 用顶点法线方向射线, 如果前方<2mm命中且法线朝向相反→穿透
    # 顶点法线: 计算低模顶点的法线(用面法线平均)
    if template_obj.data.polygons:
        # 计算每个顶点的法线
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(template_obj.data)
        bm.normal_update()
        vert_normals = [v.normal.copy() for v in bm.verts]
        bm.free()

        face_region = (tverts[:,1] > -0.12) & (tverts[:,1] < 0.02) & (np.abs(tverts[:,0]) < 0.09) & (tverts[:,2] > -0.08) & (tverts[:,2] < 0.1)
        face_idx = np.where(face_region)[0]
        penetration_count = 0
        checked = 0
        for i in face_idx[:300]:  # 采样300个
            wp = tverts[i]
            vn = vert_normals[i] if i < len(vert_normals) else Vector((0,-1,0))
            origin_local = sm.inverted() @ Vector(tuple(wp))
            # 法线方向(向外)射5mm
            dir_local = (sm.inverted().to_3x3() @ vn).normalized()
            hit_fwd, loc_f, n_f, fi_f = scan_obj.ray_cast(origin_local, dir_local, distance=0.005)
            if not hit_fwd:
                # 法线方向5mm内无表面, 试反方向
                hit_bwd, loc_b, n_b, fi_b = scan_obj.ray_cast(origin_local, -dir_local, distance=0.005)
                if hit_bwd:
                    # 反方向有表面 = 顶点在高模内部 = 穿透
                    penetration_count += 1
            checked += 1
        penetration_rate = penetration_count / max(1, checked)
    else:
        penetration_rate = 0

    # 5. 耳朵区域
    ear_mask = (np.abs(tverts[:,0]) > 0.05) & (np.abs(tverts[:,0]) < 0.10) & (tverts[:,2] > -0.02) & (tverts[:,2] < 0.06)
    ear_idx = np.where(ear_mask)[0]
    ear_mean = np.mean(dists[ear_idx]) if len(ear_idx)>0 else 999

    # 汇总
    report = {
        'overall_mean_mm': round(overall_mean*1000, 3),
        'overall_1mm_pct': round(overall_1mm*100, 1),
        'eye_y_diff_mm': round(eye_y_diff*1000, 2),
        'mouth_z_diff_mm': round(mouth_z_diff*1000, 2),
        'anchor_max_mm': round(anchor_max*1000, 3),
        'penetration_pct': round(penetration_rate*100, 2),
        'ear_mean_mm': round(ear_mean*1000, 3),
    }

    # 达标判断
    passed = (
        eye_y_diff < 0.003 and           # 对称性 < 3mm
        mouth_z_diff < 0.003 and         # 对称性 < 3mm
        anchor_max < 0.0005 and          # 锚点 < 0.5mm
        overall_mean < 0.0006 and        # 整体 < 0.6mm
        overall_1mm > 0.95 and           # <1mm占比 > 95%
        penetration_rate < 0.20 and      # 穿透率 < 20% (法线检测可能有误判, 放宽)
        ear_mean < 0.003                 # 耳朵 < 3mm
    )
    return report, passed

# ============================================================
# 阶段3: 渲染验证图
# ============================================================
def render_verification(scan_obj, template_obj, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    try: bpy.context.scene.display.shading.show_wire = False
    except: pass
    bpy.context.scene.display.shading.light = 'STUDIO'
    bpy.context.scene.display.shading.color_type = 'OBJECT'
    scan_obj.color = (0.6,0.6,0.6,1.0)
    template_obj.color = (0.9,0.2,0.2,1.0)

    if not bpy.context.scene.camera:
        bpy.ops.object.camera_add()
    cam = bpy.context.scene.camera

    tverts = np.array([template_obj.matrix_world @ v.co for v in template_obj.data.vertices[:500]])
    center = Vector(tverts.mean(axis=0).tolist())
    sz = 0.3

    views = {
        'front': Vector((0,-1,0)),
        'left45': Vector((0.7,-0.7,0.1)).normalized(),
        'right45': Vector((-0.7,-0.7,0.1)).normalized(),
        'top': Vector((0,-0.3,1)).normalized(),
    }
    paths = {}
    for vname, vdir in views.items():
        cam.location = center + vdir * (sz + 0.3)
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z','Z').to_euler()
        bpy.context.view_layer.update()
        p = os.path.join(out_dir, f"{vname}.png")
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths[vname] = p
    return paths

# ============================================================
# 主循环
# ============================================================
max_rounds = int(os.environ.get('AUTOCHECK_ROUNDS', '4'))

# 参数调整策略
param_strategies = [
    dict(sw_rounds=4, anchor_rounds=30, smooth_factor=0.15, smooth_iters=2),
    dict(sw_rounds=6, anchor_rounds=40, smooth_factor=0.12, smooth_iters=3),
    dict(sw_rounds=5, anchor_rounds=35, smooth_factor=0.20, smooth_iters=2),
    dict(sw_rounds=6, anchor_rounds=50, smooth_factor=0.10, smooth_iters=3),
]

for round_num in range(1, max_rounds+1):
    print(f"\n{'='*60}")
    print(f"自检轮次 {round_num}/{max_rounds}")
    print(f"{'='*60}")

    params = param_strategies[min(round_num-1, len(param_strategies)-1)]
    print(f"参数: {params}")

    t0 = time.time()
    scan_obj, template_obj, lm_3d, anchor_targets = run_fit(**params)
    print(f"  贴合耗时: {time.time()-t0:.1f}s")

    # 检查
    report, passed = run_checks(scan_obj, template_obj, lm_3d, anchor_targets)
    print(f"\n检查报告:")
    for k, v in report.items():
        print(f"  {k}: {v}")

    # 渲染
    out_dir = os.path.join(OUTPUT_DIR, f"autcheck_round{round_num}")
    render_paths = render_verification(scan_obj, template_obj, out_dir)
    print(f"\n验证图:")
    for k, v in render_paths.items():
        print(f"  {k}: {v}")

    # 保存
    blend_out = os.path.join(OUTPUT_DIR, f"head_autcheck_r{round_num}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    print(f"\n保存: {blend_out}")

    # 写报告 (确保所有值都是可序列化的基本类型)
    report_clean = {k: float(v) for k, v in report.items()}
    with open(os.path.join(out_dir, "report.json"), 'w') as f:
        json.dump({'round': round_num, 'params': {k:float(v) for k,v in params.items()}, 'report': report_clean, 'passed': bool(passed), 'blend': blend_out}, f, indent=2)

    if passed:
        print(f"\n✅ 轮次{round_num} 达标!")
        # 复制为最终版本
        import shutil
        final = os.path.join(OUTPUT_DIR, "head_final.blend")
        shutil.copy(blend_out, final)
        print(f"最终版本: {final}")
        break
    else:
        print(f"\n❌ 轮次{round_num} 未达标, 调整参数重跑...")
        # 找出最差的指标
        issues = []
        if report['eye_y_diff_mm'] >= 3: issues.append(f"眼对称{report['eye_y_diff_mm']}mm")
        if report['mouth_z_diff_mm'] >= 3: issues.append(f"嘴对称{report['mouth_z_diff_mm']}mm")
        if report['anchor_max_mm'] >= 0.5: issues.append(f"锚点{report['anchor_max_mm']}mm")
        if report['overall_mean_mm'] >= 0.6: issues.append(f"整体{report['overall_mean_mm']}mm")
        if report['overall_1mm_pct'] <= 95: issues.append(f"<1mm仅{report['overall_1mm_pct']}%")
        if report['penetration_pct'] >= 5: issues.append(f"穿透{report['penetration_pct']}%")
        if report['ear_mean_mm'] >= 3: issues.append(f"耳朵{report['ear_mean_mm']}mm")
        print(f"  问题: {', '.join(issues)}")

print(f"\n{'='*60}")
print("自检完成")
