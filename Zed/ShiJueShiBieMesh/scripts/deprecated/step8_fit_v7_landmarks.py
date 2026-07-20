"""
贴合 v7 - 终极版
1. 自动检测模板面部特征点（15+个）
2. 在扫描上自动找对应点
3. 特征点约束 + ARAP + 空洞排除 联合贴合
"""
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
import time, os, json

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v7"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
def setup():
    print("="*60)
    print("加载场景...")
    bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
    scan_obj = bpy.data.objects.get("Scan_Head")
    for obj in list(bpy.data.objects):
        if obj.type=='MESH' and obj!=scan_obj:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
    template_obj = None
    for obj in bpy.data.objects:
        if obj.type=='MESH' and obj!=scan_obj:
            template_obj=obj; break
    return template_obj, scan_obj

def rigid_align(template_obj, scan_obj):
    print("刚性对齐...")
    tm=template_obj.matrix_world; sm=scan_obj.matrix_world
    def bbox(obj):
        vs=[obj.matrix_world@v.co for v in obj.data.vertices]
        xs=[v.x for v in vs]; ys=[v.y for v in vs]; zs=[v.z for v in vs]
        return {'center':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
                'size':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)),
                'min':(min(xs),min(ys),min(zs)),'max':(max(xs),max(ys),max(zs))}
    tb=bbox(template_obj); sb=bbox(scan_obj)
    off=[sb['center'][i]-tb['center'][i] for i in range(3)]
    template_obj.location.x+=off[0]; template_obj.location.y+=off[1]; template_obj.location.z+=off[2]
    bpy.context.view_layer.update()
    sr=[sb['size'][i]/tb['size'][i] if tb['size'][i]>1e-6 else 1 for i in range(3)]
    us=sum(sr)/3
    template_obj.scale=(us,us,us)
    bpy.context.view_layer.update()
    print(f"  偏移={off[0]:.3f},{off[1]:.3f},{off[2]:.3f} 缩放={us:.4f}")

# ============================================================
def detect_landmarks(tm, template_obj, scan_obj, sm):
    """
    在模板上自动检测面部特征点，并映射到扫描
    返回: [(template_idx, scan_world_pos), ...]
    """
    print("\n"+"="*60)
    print("自动检测面部特征点...")
    
    # 获取模板世界坐标
    tcoords = np.array([tm @ v.co for v in template_obj.data.vertices])
    n = len(tcoords)
    
    # 建立坐标轴（假设头朝上Y，脸朝Z+）
    y_min, y_max = np.min(tcoords[:,1]), np.max(tcoords[:,1])
    z_min, z_max = np.min(tcoords[:,2]), np.max(tcoords[:,2])
    x_min, x_max = np.min(tcoords[:,0]), np.max(tcoords[:,0])
    x_center = (x_min + x_max) / 2
    y_range = y_max - y_min
    
    print(f"模板范围: X=[{x_min:.3f},{x_max:.3f}] Y=[{y_min:.3f},{y_max:.3f}] Z=[{z_min:.3f},{z_max:.3f}]")
    
    # ---- 特征点定义 ----
    features = {}
    
    # 鼻尖: 脸正面（Z最大）区域中，Y在中部偏下的Z最大值
    face_region = tcoords[(tcoords[:,2] > z_max*0.6)]
    if len(face_region)>0:
        nose_tip_idx = np.argmax(face_region[:,2])
        # 找到全局索引
        nose_z = face_region[nose_tip_idx, 2]
        nose_mask = np.abs(tcoords[:,2] - nose_z) < 0.001
        nose_indices = np.where(nose_mask)[0]
        features['nose_tip'] = nose_indices[0]
    
    # 左眼中心: Y在上半部、X<0、Z大
    eye_y_lo = y_min + y_range*0.55
    eye_y_hi = y_min + y_range*0.75
    eye_mask = (tcoords[:,1] > eye_y_lo) & (tcoords[:,1] < eye_y_hi) & (tcoords[:,2] > z_max*0.5)
    
    left_eye_mask = eye_mask & (tcoords[:,0] < x_center*0.3)
    right_eye_mask = eye_mask & (tcoords[:,0] > x_center*0.3)
    
    if np.any(left_eye_mask):
        left_eye_indices = np.where(left_eye_mask)[0]
        left_eye_z = tcoords[left_eye_indices, 2]
        features['left_eye'] = left_eye_indices[np.argmax(left_eye_z)]
    
    if np.any(right_eye_mask):
        right_eye_indices = np.where(right_eye_mask)[0]
        right_eye_z = tcoords[right_eye_indices, 2]
        features['right_eye'] = right_eye_indices[np.argmax(right_eye_z)]
    
    # 嘴角: Y在嘴部区域，Z大
    mouth_y = y_min + y_range*0.38
    mouth_y_lo = mouth_y - y_range*0.03
    mouth_y_hi = mouth_y + y_range*0.03
    mouth_mask = (tcoords[:,1] > mouth_y_lo) & (tcoords[:,1] < mouth_y_hi) & (tcoords[:,2] > z_max*0.5)
    
    left_mouth_mask = mouth_mask & (tcoords[:,0] < x_center*0.2)
    right_mouth_mask = mouth_mask & (tcoords[:,0] > x_center*0.2)
    
    if np.any(left_mouth_mask):
        lm_idx = np.where(left_mouth_mask)[0]
        features['left_mouth'] = lm_idx[np.argmax(tcoords[lm_idx, 0])]  # 最左边的
    
    if np.any(right_mouth_mask):
        rm_idx = np.where(right_mouth_mask)[0]
        features['right_mouth'] = rm_idx[np.argmin(tcoords[rm_idx, 0])]  # 最右边的
    
    # 下巴: Y最小 + Z大
    chin_mask = (tcoords[:,1] < y_min + y_range*0.15) & (tcoords[:,2] > z_max*0.3)
    if np.any(chin_mask):
        chin_idx = np.where(chin_mask)[0]
        features['chin'] = chin_idx[np.argmin(tcoords[chin_idx, 1])]
    
    # 眉心(鼻梁顶部): 两眼之间
    bridge_y = y_min + y_range*0.65
    bridge_mask = (np.abs(tcoords[:,1]-bridge_y) < y_range*0.03) & (np.abs(tcoords[:,0]) < 0.01) & (tcoords[:,2] > z_max*0.5)
    if np.any(bridge_mask):
        bridge_idx = np.where(bridge_mask)[0]
        features['nose_bridge'] = bridge_idx[np.argmax(tcoords[bridge_idx, 2])]
    
    # 额头
    forehead_y = y_min + y_range*0.85
    fh_mask = (np.abs(tcoords[:,1]-forehead_y) < y_range*0.02) & (np.abs(tcoords[:,0]) < 0.01)
    if np.any(fh_mask):
        fh_idx = np.where(fh_mask)[0]
        features['forehead'] = fh_idx[np.argmax(tcoords[fh_idx, 2])]
    
    # 左右眉弓
    brow_y = y_min + y_range*0.7
    for side, sign in [('left_brow', 1), ('right_brow', -1)]:
        bm = (tcoords[:,1] > brow_y-y_range*0.02) & (tcoords[:,1] < brow_y+y_range*0.02) & (sign*tcoords[:,0] > 0.02) & (tcoords[:,2] > z_max*0.4)
        if np.any(bm):
            idx = np.where(bm)[0]
            features[side] = idx[np.argmax(tcoords[idx, 2])]
    
    # 左右耳
    ear_y = y_min + y_range*0.55
    for side, sign in [('left_ear', 1), ('right_ear', -1)]:
        em = (tcoords[:,1] > ear_y-y_range*0.03) & (tcoords[:,1] < ear_y+y_range*0.03) & (sign*tcoords[:,0] > x_max*0.6)
        if np.any(em):
            idx = np.where(em)[0]
            features[side] = idx[np.argmax(sign*tcoords[idx, 0])]
    
    # 颈部中心
    neck_y = y_min + y_range*0.02
    nm = (np.abs(tcoords[:,1]-neck_y) < y_range*0.02) & (np.abs(tcoords[:,0]) < 0.01)
    if np.any(nm):
        idx = np.where(nm)[0]
        features['neck'] = idx[np.argmax(tcoords[idx, 2])]
    
    print(f"检测到 {len(features)} 个特征点:")
    for name, idx in features.items():
        print(f"  {name}: idx={idx}, pos=({tcoords[idx,0]:.4f},{tcoords[idx,1]:.4f},{tcoords[idx,2]:.4f})")
    
    # ---- 映射特征点到扫描 ----
    print("\n映射特征点到扫描...")
    sample_step = max(1, len(scan_obj.data.vertices)//500000)
    kd = KDTree(len(scan_obj.data.vertices)//sample_step+1)
    for i in range(0, len(scan_obj.data.vertices), sample_step):
        kd.insert(sm @ scan_obj.data.vertices[i].co, i)
    kd.balance()
    
    # 扫描的bbox
    scan_samples = [sm @ scan_obj.data.vertices[i].co for i in range(0, len(scan_obj.data.vertices), sample_step)]
    scan_coords = np.array(scan_samples)
    s_y_min, s_y_max = np.min(scan_coords[:,1]), np.max(scan_coords[:,1])
    s_z_min, s_z_max = np.min(scan_coords[:,2]), np.max(scan_coords[:,2])
    s_z_range = s_z_max - s_z_min
    s_y_range = s_y_max - s_y_min
    
    # 特征点映射策略:
    # 1. 先按相对位置映射（模板中特征在bbox中的相对位置 -> 扫描中相同相对位置）
    # 2. 然后微调（在局部区域内找几何极值点）
    
    landmarks = []  # [(template_idx, scan_pos, name)]
    
    for name, t_idx in features.items():
        tp = tcoords[t_idx]
        
        # 相对位置映射
        rel_x = (tp[0]-x_min)/(x_max-x_min) if x_max>x_min else 0.5
        rel_y = (tp[1]-y_min)/(y_max-y_min) if y_max>y_min else 0.5
        rel_z = (tp[2]-z_min)/(z_max-z_min) if z_max>z_min else 0.5
        
        # 在扫描上的粗略位置
        sp_x = s_z_min + rel_x * s_z_range  # 注意：扫描的坐标轴可能不同
        sp_y = s_y_min + (1-rel_y) * s_y_range  # Y翻转
        sp_z = s_z_min + rel_z * s_z_range
        
        # 在粗略位置找到最近扫描点
        rough_pos = Vector((sp_x, sp_y, sp_z))
        co, idx, dist = kd.find(tuple(rough_pos))
        
        # 根据特征类型微调
        refined = Vector(co)
        search_radius = 0.015  # 1.5cm搜索半径
        
        if name == 'nose_tip':
            # 找局部Z最大值
            best_z = refined.z; best_pos = refined
            for i in range(0, len(scan_obj.data.vertices), max(1, len(scan_obj.data.vertices)//500000)):
                sp = sm @ scan_obj.data.vertices[i].co
                if (sp - refined).length < search_radius and sp.z > best_z:
                    best_z = sp.z; best_pos = sp
            refined = best_pos
        
        elif name in ('left_eye', 'right_eye'):
            # 找局部Z最小值(眼窝)
            best_z = refined.z; best_pos = refined
            for i in range(0, len(scan_obj.data.vertices), max(1, len(scan_obj.data.vertices)//500000)):
                sp = sm @ scan_obj.data.vertices[i].co
                if (sp - refined).length < search_radius and sp.z < best_z:
                    best_z = sp.z; best_pos = sp
            refined = best_pos
        
        elif name == 'chin':
            # 找局部Y最小值
            best_y = refined.y; best_pos = refined
            for i in range(0, len(scan_obj.data.vertices), max(1, len(scan_obj.data.vertices)//500000)):
                sp = sm @ scan_obj.data.vertices[i].co
                if (sp - refined).length < search_radius and sp.y < best_y:
                    best_y = sp.y; best_pos = sp
            refined = best_pos
        
        landmarks.append((t_idx, refined, name))
        print(f"  {name}: template=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) -> scan=({refined.x:.4f},{refined.y:.4f},{refined.z:.4f})")
    
    return landmarks

# ============================================================
def detect_interior(template_obj, kd_scan, sm):
    """识别口腔/眼窝/鼻孔内部顶点"""
    tm = template_obj.matrix_world
    bm = bmesh.new(); bm.from_mesh(template_obj.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    vn = {}
    for v in bm.verts:
        n = Vector((0,0,0))
        for f in v.link_faces: n += f.normal
        if n.length>0: n.normalize()
        vn[v.index] = n
    
    interior = np.zeros(len(template_obj.data.vertices), dtype=bool)
    for i, v in enumerate(template_obj.data.vertices):
        wc = tm @ v.co
        n = vn.get(i, Vector((0,0,1)))
        wn = (tm.to_3x3()@n).normalized()
        co_near, idx, dn = kd_scan.find(tuple(wc))
        opp = wc - wn*0.005
        co_opp, idx2, dopp = kd_scan.find(tuple(opp))
        if dopp < dn*0.7: interior[i] = True
    bm.free()
    return interior

# ============================================================
def landmark_guided_fit(template_obj, scan_obj, landmarks, interior_mask, kd_scan, sm):
    """
    特征点约束 + ARAP 贴合
    """
    tm = template_obj.matrix_world; tm_inv = tm.inverted()
    n_verts = len(template_obj.data.vertices)
    scan_n = len(scan_obj.data.vertices)
    
    # 邻接
    edges = [(e.vertices[0],e.vertices[1]) for e in template_obj.data.edges]
    adj = {i:[] for i in range(n_verts)}
    for a,b in edges: adj[a].append(b); adj[b].append(a)
    
    # 构建 landmark约束
    lm_indices = [lm[0] for lm in landmarks]
    lm_targets = np.array([lm[1] for lm in landmarks])
    lm_weights = np.ones(len(landmarks)) * 50.0  # 特征点权重很高
    
    # 模板初始坐标 + rest edges (用于ARAP)
    template_coords = np.array([tm @ v.co for v in template_obj.data.vertices])
    rest_edges = []
    for i in range(n_verts):
        nbrs = adj[i]
        rest_edges.append([template_coords[j]-template_coords[i] for j in nbrs])
    
    V = template_coords.copy()
    
    print("\n特征点引导贴合...")
    for outer_it in range(3):
        lm_weight = 50.0 if outer_it==0 else (30.0 if outer_it==1 else 15.0)
        fit_lambda = 0.3 if outer_it==0 else (0.5 if outer_it==1 else 0.7)
        
        print(f"\n--- 轮次 {outer_it+1}/3 (lm_weight={lm_weight}, fit_lambda={fit_lambda}) ---")
        
        for inner_it in range(10):
            t0 = time.time()
            
            # 找最近扫描点
            C = np.array([kd_scan.find(tuple(V[i]))[0] for i in range(n_verts)])
            
            # 更新特征点目标（每轮重新找）
            for li, lm in enumerate(landmarks):
                tidx = lm[0]
                # 保持原来的映射目标
                lm_targets[li] = lm[1]
            
            # ARAP步骤1: 估算旋转
            rotations = np.zeros((n_verts,3,3))
            for i in range(n_verts):
                if interior_mask[i] or len(rest_edges[i])<2:
                    rotations[i] = np.eye(3); continue
                P = np.array(rest_edges[i]).T
                Q = np.array([V[j]-V[i] for j in adj[i]]).T
                try:
                    U,_,Vt=np.linalg.svd(P@Q.T)
                    R=U@Vt
                    if np.linalg.det(R)<0: Vt[-1]*=-1; R=U@Vt
                    rotations[i]=R
                except: rotations[i]=np.eye(3)
            
            # ARAP步骤2: 局部求解
            V_new = V.copy()
            
            for i in range(n_verts):
                nbrs = adj[i]
                if len(nbrs)==0: continue
                
                arap_pos = np.zeros(3); arap_w = 0
                for j in nbrs:
                    if j in rest_edges and i in rest_edges[j]:
                        try:
                            k = adj[j].index(i)
                            rest_ji = rest_edges[j][k]
                        except:
                            continue
                    else:
                        continue
                    Rj = rotations[j]
                    est = V[j] + Rj @ rest_ji
                    arap_pos += est; arap_w += 1
                
                if arap_w>0: arap_pos/=arap_w
                
                # 混合: ARAP + 目标 + 特征点约束
                w_arap = 1.0
                w_target = fit_lambda
                w_lm = 0
                
                if i in lm_indices:
                    li = lm_indices.index(i)
                    w_lm = lm_weight
                
                total_w = w_arap + w_target + w_lm
                target_pos = C[i]
                lm_pos = np.zeros(3)
                if w_lm > 0:
                    lm_pos = lm_targets[li]
                
                V_new[i] = (arap_pos*w_arap + target_pos*w_target + lm_pos*w_lm) / total_w
            
            V = V_new
            
            err = np.mean(np.linalg.norm(V-C, axis=1))
            if inner_it%3==0 or inner_it==9:
                print(f"  [{inner_it+1:2d}/10] err={err*1000:.3f}mm {time.time()-t0:.1f}s")
    
    # 写回
    for i,v in enumerate(template_obj.data.vertices):
        v.co = tm_inv @ Vector(V[i])
    template_obj.data.update()

# ============================================================
def ray_cast_refine(template_obj, scan_obj, interior_mask, sm, sm_inv):
    """ray_cast 精贴（只对表面顶点）"""
    tm = template_obj.matrix_world; tm_inv = tm.inverted()
    n_verts = len(template_obj.data.vertices)
    edges = [(e.vertices[0],e.vertices[1]) for e in template_obj.data.edges]
    adj = {i:[] for i in range(n_verts)}
    for a,b in edges: adj[a].append(b); adj[b].append(a)
    
    # 顶点法线
    bm = bmesh.new(); bm.from_mesh(template_obj.data)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    vn = {}
    for v in bm.verts:
        n=Vector((0,0,0))
        for f in v.link_faces: n+=f.normal
        if n.length>0: n.normalize()
        vn[v.index]=n
    
    print("\nray_cast 精贴...")
    for it in range(5):
        V = np.array([tm @ v.co for v in template_obj.data.vertices])
        hit=0
        for i,v in enumerate(template_obj.data.vertices):
            if interior_mask[i]: continue
            wc=tm@v.co; lc=sm_inv@wc
            n=vn.get(i,Vector((0,0,1)))
            wn=(tm.to_3x3()@n).normalized()
            ln=(sm_inv.to_3x3()@wn).normalized()
            ro=lc-ln*0.015
            h,loc,hn,fi=scan_obj.ray_cast(ro,ln,distance=0.08)
            if not h: h,loc,hn,fi=scan_obj.ray_cast(lc+ln*0.015,-ln,distance=0.08)
            if h: V[i]=sm@loc; hit+=1
        
        for i in range(n_verts):
            nbrs=adj[i]
            if not nbrs: continue
            avg=np.mean([V[j] for j in nbrs],axis=0)
            V[i]=V[i]*0.85+avg*0.15
        
        for i,v in enumerate(template_obj.data.vertices):
            v.co=tm_inv@Vector(V[i])
        template_obj.data.update()
        print(f"  [{it+1}/5] hit={hit} {time.time():.0f}s")
    bm.free()

# ============================================================
def verify_and_save(template_obj, scan_obj, interior_mask, sm, scan_n, outdir):
    print("\n验证...")
    verify_step = max(1, scan_n//1000000)
    kd_v = KDTree(scan_n//verify_step+1)
    for i in range(0, scan_n, verify_step):
        kd_v.insert(sm @ scan_obj.data.vertices[i].co,i)
    kd_v.balance()
    
    tm = template_obj.matrix_world
    Vf = np.array([tm @ v.co for v in template_obj.data.vertices])
    dists = np.array([kd_v.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
    sd = dists[~interior_mask]
    id_ = dists[interior_mask]
    
    print(f"表面: mean={np.mean(sd)*1000:.2f}mm median={np.median(sd)*1000:.2f}mm")
    print(f"内部: mean={np.mean(id_)*1000:.2f}mm median={np.median(id_)*1000:.2f}mm")
    print(f"全部: mean={np.mean(dists)*1000:.3f}mm median={np.median(dists)*1000:.3f}mm")
    print(f"<0.5mm:{np.sum(dists<0.0005)/len(dists)*100:.1f}% <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}% <2mm:{np.sum(dists<0.002)/len(dists)*100:.1f}%")
    
    print("\n保存...")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir,"MH_Head_01_fitted.blend"))
    template_obj.select_set(True)
    bpy.context.view_layer.objects.active = template_obj
    bpy.ops.export_scene.gltf(filepath=os.path.join(outdir,"MH_Head_01_fitted.glb"),
                               use_selection=True,export_format='GLB',export_apply=True)
    bpy.ops.wm.obj_export(filepath=os.path.join(outdir,"MH_Head_01_fitted.obj"),
                           export_selected_objects=True)
    json.dump({
        "verts":len(Vf),
        "interior":int(np.sum(interior_mask)),
        "surface_mean_mm":float(np.mean(sd)*1000),
        "surface_median_mm":float(np.median(sd)*1000),
        "all_mean_mm":float(np.mean(dists)*1000),
        "pct_0_5":float(np.sum(dists<0.0005)/len(dists)*100),
        "pct_1_0":float(np.sum(dists<0.001)/len(dists)*100),
    },open(os.path.join(outdir,"quality.json"),'w'),indent=2)
    

# ============================================================
# === MAIN ===
# ============================================================
template_obj, scan_obj = setup()
rigid_align(template_obj, scan_obj)

tm = template_obj.matrix_world; sm = scan_obj.matrix_world

# 构建扫描 KDTree（用于映射和贴合）
sample_step = max(1, len(scan_obj.data.vertices)//300000)
kd_scan = KDTree(len(scan_obj.data.vertices)//sample_step+1)
for i in range(0, len(scan_obj.data.vertices), sample_step):
    kd_scan.insert(sm @ scan_obj.data.vertices[i].co, i)
kd_scan.balance()

# 1. 检测特征点
landmarks = detect_landmarks(tm, template_obj, scan_obj, sm)

# 2. 识别内部顶点
interior_mask = detect_interior(template_obj, kd_scan, sm)
print(f"\n内部顶点: {np.sum(interior_mask)}")

# 3. 特征点引导贴合
landmark_guided_fit(template_obj, scan_obj, landmarks, interior_mask, kd_scan, sm)

# 4. ray_cast 收尾
sm = scan_obj.matrix_world; sm_inv = sm.inverted()
ray_cast_refine(template_obj, scan_obj, interior_mask, sm, sm_inv)

# 5. 验证+保存
verify_and_save(template_obj, scan_obj, interior_mask, sm, len(scan_obj.data.vertices), OUTPUT_DIR)

print("\noutput_v7/ 完成!")