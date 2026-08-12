
import bpy, numpy as np, json
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=SOCKET)
d = json.load(open(EYELID, encoding="utf-8"))
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
c = np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
mesh = head.data
def pip(x,z,poly):
    ins=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,zi=poly[i]; xj,zj=poly[j]
        if ((zi>z)!=(zj>z)) and (x<(xj-xi)*(z-zi)/(zj-zi)+xi): ins=not ins
        j=i
    return ins
mesh.calc_loop_triangles()
poly=[(r[0],r[2]) for r in d["L"]["rim_3d"] if r]
rim_y = np.mean([r[1] for r in d["L"]["rim_3d"] if r])
# 分层: 碗底平面(y≈rim_y+0.020) vs 侧壁 vs 脸面
for f in mesh.polygons: pass
bottom=[]; sidewall=[]; face_skin=[]
for f in mesh.polygons:
    if not pip(f.center[0],f.center[2],poly): continue
    fc_y = f.center[1]
    if fc_y > rim_y + 0.015: bottom.append(f)       # 碗底(最深处)
    elif fc_y > rim_y + 0.003: sidewall.append(f)   # 侧壁
    else: face_skin.append(f)                        # 脸面/口沿
def report(name, fs):
    if not fs: print(f"{name}: 0面"); return
    ny=np.array([f.normal[1] for f in fs])
    mn=np.array([np.array(f.normal[:]) for f in fs]).mean(0); mn/=np.linalg.norm(mn)
    ang=np.degrees(np.arccos(np.clip(np.array([np.array(f.normal[:]) for f in fs])@mn,-1,1)))
    print(f"{name}: {len(fs)}面 法线y[{ny.min():.2f},{ny.max():.2f}] 离散mean={ang.mean():.1f}° >40°:{(ang>40).sum()}")
report("碗底", bottom)
report("侧壁", sidewall)
report("脸面/口沿", face_skin)
