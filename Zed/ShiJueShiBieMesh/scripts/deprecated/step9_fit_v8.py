"""
贴合 v8 - 修复特征点映射
直接 KDTree 最近点 + 局部几何极值微调
"""
import bpy, bmesh, numpy as np, time, os, json
from mathutils import Vector
from mathutils.kdtree import KDTree

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_v8"
BLEND_FILE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\人头对齐_个人使用勿动.blend"
TEMPLATE_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 加载 ===
print("加载...")
bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
scan_obj = bpy.data.objects.get("Scan_Head")
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and obj!=scan_obj: bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.obj_import(filepath=TEMPLATE_PATH)
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=scan_obj: template_obj=obj; break

# === 对齐 ===
print("对齐...")
tm=template_obj.matrix_world; sm=scan_obj.matrix_world
def bbox(obj):
    vs=[obj.matrix_world@v.co for v in obj.data.vertices]
    xs=[v.x for v in vs];ys=[v.y for v in vs];zs=[v.z for v in vs]
    return {'c':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2),
            'sz':(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs))}
tb=bbox(template_obj); sb=bbox(scan_obj)
off=[sb['c'][i]-tb['c'][i] for i in range(3)]
template_obj.location.x+=off[0];template_obj.location.y+=off[1];template_obj.location.z+=off[2]
bpy.context.view_layer.update()
sr=[sb['sz'][i]/tb['sz'][i] if tb['sz'][i]>1e-6 else 1 for i in range(3)]
us=sum(sr)/3
template_obj.scale=(us,us,us)
bpy.context.view_layer.update()
print(f"偏移={off[0]:.3f},{off[1]:.3f},{off[2]:.3f} 缩放={us:.4f}")

tm=template_obj.matrix_world; tm_inv=tm.inverted()
sm=scan_obj.matrix_world; sm_inv=sm.inverted()
scan_n=len(scan_obj.data.vertices)

# === 扫描 KDTree ===
print("构建扫描 KDTree...")
sp=100000
ss = max(1, scan_n//sp)
kd = KDTree(scan_n//ss+1)
for i in range(0, scan_n, ss): kd.insert(sm@scan_obj.data.vertices[i].co, i)
kd.balance()
print(f"  {scan_n//ss+1:,} 点")

# === 模板顶点坐标 ===
tcoords = np.array([tm@v.co for v in template_obj.data.vertices])
n_verts = len(tcoords)
edges = [(e.vertices[0],e.vertices[1]) for e in template_obj.data.edges]
adj = {i:[] for i in range(n_verts)}
for a,b in edges: adj[a].append(b); adj[b].append(a)

# === 内部顶点识别 ===
print("识别内部顶点...")
bm0=bmesh.new();bm0.from_mesh(template_obj.data)
bm0.verts.ensure_lookup_table();bm0.faces.ensure_lookup_table()
vn={}
for v in bm0.verts:
    n=Vector((0,0,0))
    for f in v.link_faces: n+=f.normal
    if n.length>0: n.normalize()
    vn[v.index]=n
interior=np.zeros(n_verts,dtype=bool)
for i,v in enumerate(template_obj.data.vertices):
    wc=tm@v.co; n=vn.get(i,Vector((0,0,1)))
    wn=(tm.to_3x3()@n).normalized()
    cn,ix,dn=kd.find(tuple(wc))
    co,ix2,dopp=kd.find(tuple(wc-wn*0.005))
    if dopp<dn*0.7: interior[i]=True
print(f"  内部: {np.sum(interior)}")

# === 特征点检测 ===
print("\n特征点检测...")
y_min,y_max=np.min(tcoords[:,1]),np.max(tcoords[:,1])
z_min,z_max=np.min(tcoords[:,2]),np.max(tcoords[:,2])
x_range=np.max(tcoords[:,0])-np.min(tcoords[:,0])
yr=y_max-y_min; zr=z_max-z_min; xm=(np.min(tcoords[:,0])+np.max(tcoords[:,0]))/2

features={}

# 鼻尖: 脸正面的Z最大值
face_fwd = tcoords[tcoords[:,2]>z_max-0.1*zr]
if len(face_fwd)>0:
    fi=np.argmax(face_fwd[:,2])
    features['nose_tip']=np.where(np.all(np.abs(tcoords-face_fwd[fi])<0.001,axis=1))[0][0]

# 眼窝: Y在上半部, Z大, 找Z局部最小
eye_y=y_min+0.55*yr; eye_hi=y_min+0.75*yr
eye_m=(tcoords[:,1]>eye_y)&(tcoords[:,1]<eye_hi)&(tcoords[:,2]>z_max-0.3*zr)
for side,s in [('left_eye',-1),('right_eye',1)]:
    m=eye_m&(s*tcoords[:,0]>0.01) if np.any(eye_m) else np.zeros(n_verts,dtype=bool)
    if np.any(m):
        idx=np.where(m)[0]
        features[side]=idx[np.argmin(tcoords[idx,2])]  # Z最小=眼窝最深

# 嘴角: Y在嘴部, Z大
my=y_min+0.38*yr
mm=(np.abs(tcoords[:,1]-my)<0.03*yr)&(tcoords[:,2]>z_max-0.3*zr)
for side,s in [('left_mouth',-1),('right_mouth',1)]:
    m=mm&(s*tcoords[:,0]>0.005)
    if np.any(m):
        idx=np.where(m)[0]
        features[side]=idx[np.argmax(s*tcoords[idx,0])]

# 下巴
cm=tcoords[:,1]<y_min+0.15*yr
if np.any(cm):
    idx=np.where(cm)[0]
    features['chin']=idx[np.argmax(tcoords[idx,2])]

# 眉心
bm0=tcoords[:,1]>y_min+0.65*yr
bm1=tcoords[:,1]<y_min+0.72*yr
bm2=np.abs(tcoords[:,0])<0.01
bm=bm0&bm1&bm2
if np.any(bm):
    idx=np.where(bm)[0]
    features['nose_bridge']=idx[np.argmax(tcoords[idx,2])]

# 额头
fh=(tcoords[:,1]>y_min+0.85*yr)&(np.abs(tcoords[:,0])<0.01)
if np.any(fh):
    idx=np.where(fh)[0]
    features['forehead']=idx[np.argmax(tcoords[idx,2])]

# 左右颧骨
ch_y=y_min+0.5*yr
for side,s in [('left_cheek',-1),('right_cheek',1)]:
    cm0=(np.abs(tcoords[:,1]-ch_y)<0.03*yr)&(tcoords[:,2]>z_max-0.2*zr)
    cm1=s*tcoords[:,0]>0.03
    if np.any(cm0&cm1):
        idx=np.where(cm0&cm1)[0]
        features[side]=idx[np.argmax(tcoords[idx,2])]

# 颈部
nk=tcoords[:,1]<y_min+0.03*yr
if np.any(nk):
    idx=np.where(nk)[0]
    features['neck_bottom']=idx[np.argmin(tcoords[idx,1])]

print(f"检测到 {len(features)} 个特征点:")
for name,i in features.items():
    print(f"  {name}: ({tcoords[i,0]:.4f},{tcoords[i,1]:.4f},{tcoords[i,2]:.4f})")

# === 特征点映射到扫描 ===
print("\n映射特征点到扫描...")
lm = []  # [(template_idx, scan_world_pos, weight)]
for name,ti in features.items():
    tp = tcoords[ti]
    # 直接KDTree最近点作为初始映射
    co,ix,dist = kd.find(tuple(tp))
    refined = Vector(co)
    
    # 局部极值微调
    radius = 0.02
    if name=='nose_tip':
        best_z=refined.z; bp=refined
        for i in range(0,scan_n,max(1,scan_n//300000)):
            sp=sm@scan_obj.data.vertices[i].co
            if (sp-refined).length<radius and sp.z>best_z: best_z=sp.z;bp=sp
        refined=bp
    elif name in ('left_eye','right_eye'):
        best_z=refined.z; bp=refined
        for i in range(0,scan_n,max(1,scan_n//300000)):
            sp=sm@scan_obj.data.vertices[i].co
            if (sp-refined).length<radius*1.5 and sp.z<best_z: best_z=sp.z;bp=sp
        refined=bp
    elif name=='chin':
        best_y=refined.y; bp=refined
        for i in range(0,scan_n,max(1,scan_n//300000)):
            sp=sm@scan_obj.data.vertices[i].co
            if (sp-refined).length<radius and sp.y<best_y: best_y=sp.y;bp=sp
        refined=bp
    
    lm.append((ti, refined, name))
    print(f"  {name}: t=({tp[0]:.4f},{tp[1]:.4f},{tp[2]:.4f}) -> s=({refined.x:.4f},{refined.y:.4f},{refined.z:.4f}) d={dist*1000:.2f}mm")

# === 贴合 ===
print("\n"+"="*60)
print("特征点引导贴合...")

# rest edges (ARAP)
template_coords = tcoords.copy()
rest_edges=[]
for i in range(n_verts):
    rest_edges.append([template_coords[j]-template_coords[i] for j in adj[i]])

V = template_coords.copy()
surface_mask = ~interior
lm_indices = [l[0] for l in lm]

for outer in range(3):
    lm_w = 80.0 if outer==0 else (40.0 if outer==1 else 20.0)
    fl = 0.3 if outer==0 else (0.6 if outer==1 else 0.85)
    print(f"\n--- 轮{outer+1} (lm_w={lm_w}, fit_lambda={fl}) ---")
    
    for it in range(12):
        t0=time.time()
        C = np.array([kd.find(tuple(V[i]))[0] for i in range(n_verts)])
        lm_targets = np.array([l[1] for l in lm])
        
        # ARAP旋转
        rots=np.zeros((n_verts,3,3))
        for i in range(n_verts):
            if interior[i] or len(rest_edges[i])<2: rots[i]=np.eye(3); continue
            P=np.array(rest_edges[i]).T
            Q=np.array([V[j]-V[i] for j in adj[i]]).T
            try:
                U,_,Vt=np.linalg.svd(P@Q.T)
                R=U@Vt
                if np.linalg.det(R)<0: Vt[-1]*=-1; R=U@Vt
                rots[i]=R
            except: rots[i]=np.eye(3)
        
        V_new=V.copy()
        for i in range(n_verts):
            nbrs=adj[i]
            if len(nbrs)==0: continue
            arap=np.zeros(3); aw=0
            for j in nbrs:
                if i in adj[j]:
                    try:
                        ki=adj[j].index(i)
                        re=rest_edges[j][ki]
                    except: continue
                    V_new[j]  # use current
                    est=V[j]+rots[j]@re
                    arap+=est; aw+=1
            if aw>0: arap/=aw
            
            wa=1.0; wt=fl; wl=0
            if i in lm_indices:
                li=lm_indices.index(i)
                wl=lm_w
            tw=wa+wt+wl
            if not interior[i]:
                V_new[i]=(arap*wa+C[i]*wt+(lm_targets[li] if wl>0 else np.zeros(3))*wl)/tw
            else:
                V_new[i]=arap  # 内部顶点纯ARAP
        
        V=V_new
        err=np.mean(np.linalg.norm(V-C,axis=1))
        if it%3==0 or it==11:
            print(f"  [{it+1:2d}/12] err={err*1000:.3f}mm {time.time()-t0:.1f}s")

# 写回
for i,v in enumerate(template_obj.data.vertices):
    v.co=tm_inv@Vector(V[i])
template_obj.data.update()

# === ray_cast ===
print("\nray_cast 精贴...")
tm=template_obj.matrix_world; tm_inv=tm.inverted()
sm=scan_obj.matrix_world; sm_inv=sm.inverted()
for it in range(3):
    V=np.array([tm@v.co for v in template_obj.data.vertices])
    hit=0
    for i,v in enumerate(template_obj.data.vertices):
        if interior[i]: continue
        wc=tm@v.co; lc=sm_inv@wc
        n=vn.get(i,Vector((0,0,1)))
        wn=(tm.to_3x3()@n).normalized()
        ln=(sm_inv.to_3x3()@wn).normalized()
        ro=lc-ln*0.015
        h,loc,hn,fi=scan_obj.ray_cast(ro,ln,distance=0.1)
        if not h: h,loc,hn,fi=scan_obj.ray_cast(lc+ln*0.015,-ln,distance=0.1)
        if h: V[i]=sm@loc; hit+=1
    for i in range(n_verts):
        nbrs=adj[i]
        if not nbrs: continue
        avg=np.mean([V[j] for j in nbrs],axis=0)
        V[i]=V[i]*0.85+avg*0.15
    for i,v in enumerate(template_obj.data.vertices):
        v.co=tm_inv@Vector(V[i])
    template_obj.data.update()
    print(f"  [{it+1}/3] hit={hit}")

# === 验证 ===
print("\n验证...")
vs=max(1,scan_n//1000000)
kdv=KDTree(scan_n//vs+1)
for i in range(0,scan_n,vs): kdv.insert(sm@scan_obj.data.vertices[i].co,i)
kdv.balance()
tm=template_obj.matrix_world
Vf=np.array([tm@v.co for v in template_obj.data.vertices])
d=np.array([kdv.find(tuple(Vf[i]))[2] for i in range(len(Vf))])
sd=d[~interior]; id_=d[interior]
print(f"表面: mean={np.mean(sd)*1000:.2f}mm med={np.median(sd)*1000:.2f}mm")
print(f"内部: mean={np.mean(id_)*1000:.2f}mm med={np.median(id_)*1000:.2f}mm")
print(f"全部: mean={np.mean(d)*1000:.3f}mm <0.5:{np.sum(d<0.0005)/len(d)*100:.1f}% <1:{np.sum(d<0.001)/len(d)*100:.1f}%")

# === 保存 ===
print("\n保存...")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.blend"))
template_obj.select_set(True); bpy.context.view_layer.objects.active=template_obj
bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR,"MH_Head_01_fitted.glb"),
                           use_selection=True,export_format='GLB',export_apply=True)
json.dump({"surface_mean":float(np.mean(sd)*1000),"surface_median":float(np.median(sd)*1000),
           "all_mean":float(np.mean(d)*1000),"features":len(features)},
          open(os.path.join(OUTPUT_DIR,"quality.json"),'w'),indent=2)
print(f"output_v8/ 完成! {len(features)} 特征点引导")