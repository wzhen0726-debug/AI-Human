"""
v3 管线: 特征点精确对齐 + 全478点锚定 + 法线方向修正
关键修复: 模板和扫描的坐标系不同, 用特征点(非质心)对齐
"""
import bpy, os, numpy as np, math, cv2, json, sys, time
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test01"
SCAN_PATH = os.path.join(ROOT, "data", "high_poly", "Scan_Head_Lv5.obj")
TPL_PATH = os.path.join(ROOT, "data", "low_poly", "MH_Head_01.obj")
MODEL_PATH = os.path.join(ROOT, "data", "models", "face_landmarker.task")
LM_JSON = os.path.join(ROOT, "data", "low_poly", "template_landmarks.json")
OUT_DIR = os.path.join(ROOT, "output", "rounds")
os.makedirs(OUT_DIR, exist_ok=True)

with open(LM_JSON) as f: tpl_lm = json.load(f)

MP_KEY = {
    'nose_tip':1,'right_eye_inner':133,'right_eye_outer':33,
    'left_eye_inner':362,'left_eye_outer':263,
    'right_mouth_corner':61,'left_mouth_corner':291,
    'chin':199,'forehead':10,'nose_bridge':6,
    'right_brow':105,'left_brow':334,
}

def bbox_w(obj):
    vs=[obj.matrix_world @ v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return dict(center=(Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2))),
                min=(min(xs),min(ys),min(zs)),max=(max(xs),max(ys),max(zs)),
                size=(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))

# ===== 阶段 1: 导入扫描 + 渲染 + MediaPipe =====
print("1. 导入扫描 + 6方向渲染")
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath=SCAN_PATH)
scan=[o for o in bpy.data.objects if o.type=='MESH'][0]
scan.name="Scan_Head"
bpy.context.view_layer.objects.active=scan; scan.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
# 居中
sb=bbox_w(scan); scan.location-=sb['center']
bpy.context.view_layer.update(); bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
sb=bbox_w(scan); center=sb['center']; sz=max(sb['size'])
print(f"  扫描: {len(scan.data.vertices):,}v size=({sb['size'][0]*1000:.0f},{sb['size'][1]*1000:.0f},{sb['size'][2]*1000:.0f})mm")

bpy.context.scene.render.engine='BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x=512; bpy.context.scene.render.resolution_y=512
bpy.ops.object.light_add(type='SUN',location=(0,0,10)); bpy.context.active_object.data.energy=5.0
bpy.ops.object.camera_add(); cam=bpy.context.active_object; bpy.context.scene.camera=cam
dirs={'+Y':(0,1,0),'-Y':(0,-1,0),'+X':(1,0,0),'-X':(-1,0,0),'+Z':(0,0,1),'-Z':(0,0,-1)}
paths={}
for n,d in dirs.items():
    cam.location=center+Vector(d)*(sz+0.5)
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Z').to_euler()
    bpy.context.view_layer.update()
    p=os.path.join(OUT_DIR,f"scan_{n}.png"); bpy.context.scene.render.filepath=p
    bpy.ops.render.render(write_still=True); paths[n]=p

print("2. MediaPipe")
import mediapipe as mp
from mediapipe.tasks import python as mp_py
from mediapipe.tasks.python import vision
opt=vision.FaceLandmarkerOptions(base_options=mp_py.BaseOptions(model_asset_path=MODEL_PATH),running_mode=vision.RunningMode.IMAGE,num_faces=1)
det=vision.FaceLandmarker.create_from_options(opt)
best_lm=None;best_n=0;best_dir=None
for n,p in paths.items():
    img=cv2.resize(cv2.imread(p),(256,256));rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    r=det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
    if r.face_landmarks:
        c=len(r.face_landmarks[0])
        if c>best_n:best_lm=r.face_landmarks[0];best_n=c;best_dir=n
det.close()
print(f"  BEST: {best_dir} ({best_n}pts)")

# ===== 阶段 2: 2D→3D映射 =====
print("3. 2D→3D映射")
d=dirs[best_dir];cam.location=center+Vector(d)*(sz+0.5)
cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Z').to_euler()
bpy.context.view_layer.update()
sm=scan.matrix_world;cam_pos=cam.matrix_world.to_translation();fov=cam.data.angle;h=w=256
def map_pt(idx):
    lm=best_lm[idx];px,py=lm.x*w,lm.y*h
    nx,ny=(px/w)*2-1,1-(py/h)*2
    rc=Vector((nx*math.tan(fov/2),ny*math.tan(fov/2),-1)).normalized()
    rw=(cam.matrix_world.to_3x3()@rc).normalized()
    ol=sm.inverted()@cam_pos;dl=(sm.inverted().to_3x3()@rw).normalized()
    hit,loc,n,fi=scan.ray_cast(ol,dl,distance=2.0)
    if not hit:hit,loc,n,fi=scan.ray_cast(ol,-dl,distance=2.0)
    return sm@loc if hit else None

lm3d={}
for name,idx in MP_KEY.items():
    p=map_pt(idx)
    if p:lm3d[name]=p
print(f"  核心点: {len(lm3d)}/{len(MP_KEY)}")

# ===== 阶段 3: 导入模板 + 特征点对齐 (非质心!) =====
print("4. 导入模板 + 特征点对齐")
bpy.ops.wm.obj_import(filepath=TPL_PATH)
tpl=[o for o in bpy.data.objects if o.type=='MESH' and o!=scan][0]
bpy.context.view_layer.objects.active=tpl; tpl.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)

tm=tpl.matrix_world
# 模板特征点世界坐标
t_feat={}
for name,idx in tpl_lm.items():
    if name in lm3d and name in MP_KEY:
        t_feat[name]=(tm @ tpl.data.vertices[idx].co, idx)

print(f"  匹配特征点: {len(t_feat)}")
# 用特征点做最优刚性对齐 (Procrustes)
t_pts=np.array([v[0].x for v in t_feat.values()]+[v[0].y for v in t_feat.values()]+[v[0].z for v in t_feat.values()]).reshape(-1,3)
# 重新取
t_pts=np.array([[t_feat[n][0].x,t_feat[n][0].y,t_feat[n][0].z] for n in t_feat])
s_pts=np.array([[lm3d[n].x,lm3d[n].y,lm3d[n].z] for n in t_feat])

# 1. 平移: 特征点质心对齐
tc=t_pts.mean(axis=0); sc=s_pts.mean(axis=0)
tpl.location+=Vector((sc[0]-tc[0],sc[1]-tc[1],sc[2]-tc[2]))
bpy.context.view_layer.update()
print(f"  质心偏移: ({(sc[0]-tc[0])*1000:.1f},{(sc[1]-tc[1])*1000:.1f},{(sc[2]-tc[2])*1000:.1f})mm")

# 2. 缩放: 特征点距离均值比
tm=tpl.matrix_world
t_pts2=np.array([(tm @ tpl.data.vertices[t_feat[n][1]].co)[:] for n in t_feat])
t_dist=np.mean([np.linalg.norm(t_pts2[i]-t_pts2[j]) for i in range(len(t_pts2)) for j in range(i+1,len(t_pts2))])
s_dist=np.mean([np.linalg.norm(s_pts[i]-s_pts[j]) for i in range(len(s_pts)) for j in range(i+1,len(s_pts))])
scale=s_dist/max(t_dist,1e-6)
tpl.scale=(scale,scale,scale)
bpy.context.view_layer.update()
print(f"  缩放: {scale:.4f}")

# 3. 再平移修正 (缩放后质心偏移)
tm=tpl.matrix_world
t_pts3=np.array([(tm @ tpl.data.vertices[t_feat[n][1]].co)[:] for n in t_feat])
tc3=t_pts3.mean(axis=0)
tpl.location+=Vector((sc[0]-tc3[0],sc[1]-tc3[1],sc[2]-tc3[2]))
bpy.context.view_layer.update()

# 验证对齐
tm=tpl.matrix_world
max_err=0
for n in t_feat:
    wp=tm @ tpl.data.vertices[t_feat[n][1]].co
    err=(wp-lm3d[n]).length
    if err>max_err:max_err=err
    print(f"  {n}: err={err*1000:.1f}mm")
print(f"  对齐后最大偏差: {max_err*1000:.1f}mm")

# ===== 阶段 4: Shrinkwrap =====
print("5. Shrinkwrap (NEAREST)")
for i in range(4):
    sw=tpl.modifiers.new("SW",'SHRINKWRAP')
    sw.target=scan; sw.wrap_method='NEAREST_SURFACEPOINT'; sw.wrap_mode='ON_SURFACE'; sw.offset=0.0
    bpy.ops.object.modifier_apply(modifier="SW")
    cs=tpl.modifiers.new("CS",'CORRECTIVE_SMOOTH')
    cs.iterations=2; cs.smooth_type='SIMPLE'; cs.factor=0.15
    bpy.ops.object.modifier_apply(modifier="CS")
    print(f"  [{i+1}/4]")

# ===== 阶段 5: 特征点锚定 =====
print("6. 特征点锚定")
tm=tpl.matrix_world; tm_inv=tm.inverted()
mesh=tpl.data
adj=[set() for _ in range(len(mesh.vertices))]
for e in mesh.edges:
    adj[e.vertices[0]].add(e.vertices[1]); adj[e.vertices[1]].add(e.vertices[0])
adj=[list(s) for s in adj]

anchors={}
for n in t_feat:
    idx=t_feat[n][1]
    anchors[idx]=tm_inv @ lm3d[n]

for it in range(25):
    alpha=0.3+0.5*(it/24)  # 0.3→0.8 (不拉到100%, 留弹簧余量)
    smooth_f=0.35-0.25*(it/24)
    for vi,tgt in anchors.items():
        mesh.vertices[vi].co=mesh.vertices[vi].co.lerp(tgt,alpha)
    new_co=[None]*len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        nb=adj[i]
        if nb:
            avg=Vector((0,0,0))
            for ni in nb: avg+=mesh.vertices[ni].co
            avg/=len(nb)
            if i in anchors:
                # 锚点也平滑, 但权重小(弹簧), 避免pinch
                new_co[i]=mesh.vertices[i].co.lerp(avg,smooth_f*0.3)
            else:
                new_co[i]=mesh.vertices[i].co.lerp(avg,smooth_f)
        else:
            new_co[i]=mesh.vertices[i].co.copy()
    for i in range(len(mesh.vertices)):
        mesh.vertices[i].co=new_co[i]
    if it%5==4:
        me=max((mesh.vertices[vi].co-tgt).length for vi,tgt in anchors.items())
        print(f"  [iter {it+1}/25] max_err={me*1000:.1f}mm smooth={smooth_f:.2f}")
mesh.update()

# 锚定后全局平滑: 消除局部扭曲(法线不一致)
print("  锚定后全局平滑(3轮)")
for smooth_round in range(3):
    sf=0.2-smooth_round*0.05  # 0.20, 0.15, 0.10
    new_co=[None]*len(mesh.vertices)
    for i in range(len(mesh.vertices)):
        if i in anchors:
            new_co[i]=mesh.vertices[i].co.copy()
        else:
            nb=adj[i]
            if nb:
                avg=Vector((0,0,0))
                for ni in nb: avg+=mesh.vertices[ni].co
                avg/=len(nb)
                new_co[i]=mesh.vertices[i].co.lerp(avg,sf)
            else:
                new_co[i]=mesh.vertices[i].co.copy()
    for i in range(len(mesh.vertices)):
        mesh.vertices[i].co=new_co[i]
mesh.update()
print("  全局平滑完成")

# 边长均匀化: 拉散Shrinkwrap导致的叠合顶点(如鼻梁pinch)
# 已移除: 均匀化后SW2会再次压回, 无效
# 改为: SW2使用PROJECT模式避免叠合

# 表面修正: NEAREST + CorrectiveSmooth (恢复v3.4配置)
sw2=tpl.modifiers.new("SW2",'SHRINKWRAP')
sw2.target=scan; sw2.wrap_method='NEAREST_SURFACEPOINT'; sw2.wrap_mode='ON_SURFACE'; sw2.offset=0.0
bpy.ops.object.modifier_apply(modifier="SW2")
cs2=tpl.modifiers.new("CS2",'CORRECTIVE_SMOOTH')
cs2.iterations=2; cs2.smooth_type='SIMPLE'; cs2.factor=0.15
bpy.ops.object.modifier_apply(modifier="CS2")

# 不拉回锚点! 只对pinch区域做Taubin平滑, 其他顶点不动
print("  表面后选择性Taubin(仅pinch区域)")
# 先找出pinch顶点: 边长 < 邻居边长均值*0.4
pinch_verts = set()
tm_p = tpl.matrix_world
for i in range(len(tpl.data.vertices)):
    if i in anchors:
        continue
    w = tm_p @ tpl.data.vertices[i].co
    if abs(w.x) > 0.05:  # 跳过耳朵
        continue
    nb = adj[i]
    if not nb:
        continue
    my_co = tpl.data.vertices[i].co
    edge_lens = [(tpl.data.vertices[ni].co - my_co).length for ni in nb]
    avg_len = sum(edge_lens) / len(edge_lens)
    if any(el < avg_len * 0.4 for el in edge_lens):
        pinch_verts.add(i)
# 扩展: 加入pinch顶点的直接邻居(也限面部)
pinch_zone = set(pinch_verts)
for vi in pinch_verts:
    for ni in adj[vi]:
        w_ni = tm_p @ tpl.data.vertices[ni].co
        if ni not in anchors and abs(w_ni.x) < 0.05:
            pinch_zone.add(ni)
print(f"  pinch区域顶点: {len(pinch_zone)}")

for _ in range(3):
    # 正向 λ=0.5
    new_co = [None] * len(tpl.data.vertices)
    for i in range(len(tpl.data.vertices)):
        if i in pinch_zone:
            nb = adj[i]
            if nb:
                avg = Vector((0,0,0))
                for ni in nb: avg += tpl.data.vertices[ni].co
                avg /= len(nb)
                new_co[i] = tpl.data.vertices[i].co.lerp(avg, 0.5)
            else:
                new_co[i] = tpl.data.vertices[i].co.copy()
        else:
            new_co[i] = tpl.data.vertices[i].co.copy()
    for i in range(len(tpl.data.vertices)):
        tpl.data.vertices[i].co = new_co[i]
    tpl.data.update()
    # 逆向 μ=-0.53
    new_co = [None] * len(tpl.data.vertices)
    for i in range(len(tpl.data.vertices)):
        if i in pinch_zone:
            nb = adj[i]
            if nb:
                avg = Vector((0,0,0))
                for ni in nb: avg += tpl.data.vertices[ni].co
                avg /= len(nb)
                new_co[i] = tpl.data.vertices[i].co.lerp(avg, -0.53)
            else:
                new_co[i] = tpl.data.vertices[i].co.copy()
        else:
            new_co[i] = tpl.data.vertices[i].co.copy()
    for i in range(len(tpl.data.vertices)):
        tpl.data.vertices[i].co = new_co[i]
    tpl.data.update()
print("  选择性Taubin完成")

# (pinch修复已移至阶段5.6, 自相交修复之后)

# ===== 阶段 5.5: 自相交修复 (排除耳朵) =====
print("5.5 自相交修复 (非耳朵区域)")
from mathutils.bvhtree import BVHTree

# 1. 检测自相交面
bvh_tpl = BVHTree.FromObject(tpl, bpy.context.evaluated_depsgraph_get())
overlaps = bvh_tpl.overlap(bvh_tpl)

# 过滤相邻面（共享顶点的不算自相交）
intersecting_faces = set()
for i, j in overlaps:
    fi = tpl.data.polygons[i]
    fj = tpl.data.polygons[j]
    if not (set(fi.vertices) & set(fj.vertices)):
        intersecting_faces.add(i)
        intersecting_faces.add(j)

print(f"  自相交面: {len(intersecting_faces)}")

# 2. 修复自相交顶点：排除耳朵区域 (|X| > 0.05m)
if len(intersecting_faces) > 0:
    # 收集受影响的顶点
    bad_verts = set()
    tm = tpl.matrix_world
    for fi in intersecting_faces:
        for v_idx in tpl.data.polygons[fi].vertices:
            w_pos = tm @ tpl.data.vertices[v_idx].co
            # 排除耳朵区域 (|X| > 50mm)
            if abs(w_pos.x) < 0.05:
                bad_verts.add(v_idx)
    
    # 保护锚点（特征点不能动）
    bad_verts -= set(anchors.keys())
    print(f"  受影响顶点 (非耳朵): {len(bad_verts)} (排除锚点和耳朵)")
    
    # Laplacian 松弛: 把折叠顶点拉向邻居平均，展开交叉面
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bvh_scan = BVHTree.FromObject(scan, depsgraph)
    tm_inv = tm.inverted()
    
    for iteration in range(3):
        new_co = [None] * len(tpl.data.vertices)
        for i in range(len(tpl.data.vertices)):
            if i in bad_verts:
                nb = adj[i]
                if nb:
                    avg = Vector((0,0,0))
                    for ni in nb: avg += tpl.data.vertices[ni].co
                    avg /= len(nb)
                    new_co[i] = tpl.data.vertices[i].co.lerp(avg, 0.5)
                else:
                    new_co[i] = tpl.data.vertices[i].co.copy()
            else:
                new_co[i] = tpl.data.vertices[i].co.copy()
        for i in range(len(tpl.data.vertices)):
            tpl.data.vertices[i].co = new_co[i]
        tpl.data.update()
    print(f"  Laplacian松弛: 3轮完成")
    
    # 重投影: 松弛后用 find_nearest 贴回扫描表面
    fixed_count = 0
    for vi in bad_verts:
        v = tpl.data.vertices[vi]
        w_pos = tm @ v.co
        best_loc, _, _, _ = bvh_scan.find_nearest(w_pos)
        if best_loc:
            v.co = tm_inv @ best_loc
            fixed_count += 1
    tpl.data.update()
    print(f"  重投影顶点: {fixed_count}")
    
    # 3. 局部平滑（只针对修复区域）
    if fixed_count > 0:
        print("  局部平滑")
        for _ in range(2):
            new_co = [None] * len(tpl.data.vertices)
            for i in range(len(tpl.data.vertices)):
                if i in bad_verts:
                    nb = adj[i]
                    if nb:
                        avg = Vector((0,0,0))
                        for ni in nb: avg += tpl.data.vertices[ni].co
                        avg /= len(nb)
                        new_co[i] = tpl.data.vertices[i].co.lerp(avg, 0.3)
                    else:
                        new_co[i] = tpl.data.vertices[i].co.copy()
                else:
                    new_co[i] = tpl.data.vertices[i].co.copy()
            for i in range(len(tpl.data.vertices)):
                tpl.data.vertices[i].co = new_co[i]
        tpl.data.update()

# ===== 阶段 5.6: 最终pinch修复 (自相交修复之后) =====
print("5.6 最终pinch修复")
_severe = set()
for i in range(len(tpl.data.vertices)):
    if i in anchors:
        continue
    w = tpl.matrix_world @ tpl.data.vertices[i].co
    if abs(w.x) > 0.05:
        continue
    nb = adj[i]
    if not nb:
        continue
    my_co = tpl.data.vertices[i].co
    for ni in nb:
        el = (tpl.data.vertices[ni].co - my_co).length
        if el < 0.0005:
            _severe.add(i)
            break

processed = set()
for vi in _severe:
    if vi in processed:
        continue
    nb = adj[vi]
    if not nb:
        continue
    my_co = tpl.data.vertices[vi].co.copy()
    for ni in nb:
        if ni in processed or ni in anchors:
            continue
        el = (tpl.data.vertices[ni].co - my_co).length
        if el < 0.0005 and el > 1e-9:
            direction = (my_co - tpl.data.vertices[ni].co).normalized()
            all_lens = [(tpl.data.vertices[n2].co - my_co).length for n2 in nb]
            target = sum(all_lens) / len(all_lens)
            push_dist = (target - el) / 2
            tpl.data.vertices[vi].co = my_co + direction * push_dist
            tpl.data.vertices[ni].co = tpl.data.vertices[ni].co - direction * push_dist
            processed.add(vi)
            processed.add(ni)
            break
tpl.data.update()
print(f"  修复pinch对: {len(processed)//2} (第1轮)")

# 第2轮: 检测残余pinch
_severe2 = set()
for i in range(len(tpl.data.vertices)):
    if i in anchors:
        continue
    w = tpl.matrix_world @ tpl.data.vertices[i].co
    if abs(w.x) > 0.05:
        continue
    nb = adj[i]
    if not nb:
        continue
    my_co = tpl.data.vertices[i].co
    for ni in nb:
        el = (tpl.data.vertices[ni].co - my_co).length
        if el < 0.0005:
            _severe2.add(i)
            break
processed2 = set()
for vi in _severe2:
    if vi in processed2:
        continue
    nb = adj[vi]
    if not nb:
        continue
    my_co = tpl.data.vertices[vi].co.copy()
    for ni in nb:
        if ni in processed2 or ni in anchors:
            continue
        el = (tpl.data.vertices[ni].co - my_co).length
        if el < 0.0005 and el > 1e-9:
            direction = (my_co - tpl.data.vertices[ni].co).normalized()
            all_lens = [(tpl.data.vertices[n2].co - my_co).length for n2 in nb]
            target = sum(all_lens) / len(all_lens)
            push_dist = (target - el) / 2
            tpl.data.vertices[vi].co = my_co + direction * push_dist
            tpl.data.vertices[ni].co = tpl.data.vertices[ni].co - direction * push_dist
            processed2.add(vi)
            processed2.add(ni)
            break
tpl.data.update()
print(f"  修复pinch对: {len(processed2)//2} (第2轮)")

# ===== 阶段 6: 验证 =====
print("7. 验证")
tm=tpl.matrix_world
# 特征点偏差
for n in t_feat:
    wp=tm @ tpl.data.vertices[t_feat[n][1]].co
    err=(wp-lm3d[n]).length
    print(f"  {n}: {err*1000:.2f}mm")

# 整体距离
scan_n=len(scan.data.vertices)
step=max(1,scan_n//200000)
kdv=KDTree(scan_n//step+10)
for i in range(0,scan_n,step):
    kdv.insert(sm @ scan.data.vertices[i].co,i)
kdv.balance()
vf=np.array([tm @ v.co for v in tpl.data.vertices])
dists=np.array([kdv.find(tuple(vf[i]))[2] for i in range(len(vf))])
print(f"  overall: mean={np.mean(dists)*1000:.3f}mm <1mm:{np.sum(dists<0.001)/len(dists)*100:.1f}%")

# 对称性
eye_m=(vf[:,2]>0.025)&(vf[:,2]<0.055)&(vf[:,1]>-0.06)&(vf[:,1]<-0.02)
ev=vf[eye_m]
le=ev[ev[:,0]>0];re=ev[ev[:,0]<0]
if len(le)>0 and len(re)>0:
    print(f"  eye_y_diff: {abs(le[:,1].mean()-re[:,1].mean())*1000:.2f}mm")
mouth_m=(vf[:,2]>-0.06)&(vf[:,2]<-0.02)&(vf[:,1]>-0.08)&(vf[:,1]<-0.04)
mv=vf[mouth_m]
lm_=mv[mv[:,0]>0];rm_=mv[mv[:,0]<0]
if len(lm_)>0 and len(rm_)>0:
    print(f"  mouth_z_diff: {abs(lm_[:,2].mean()-rm_[:,2].mean())*1000:.2f}mm")

# ===== 阶段 7: 保存 =====
out=os.path.join(OUT_DIR,"head_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"8. 保存: {out}")
