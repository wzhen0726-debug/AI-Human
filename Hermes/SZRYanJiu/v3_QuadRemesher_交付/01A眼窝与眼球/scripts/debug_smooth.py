
import bpy, numpy as np, bmesh, json
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
EYELID = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=SOCKET)
d = json.load(open(EYELID, encoding="utf-8"))
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
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
c=np.array([r for r in d["L"]["rim_3d"] if r]).mean(0)
# 碗内面(多边形内, y>中心=凹陷部分)
faces=[f for f in mesh.polygons if pip(f.center[0],f.center[2],poly) and f.center[1]>c[1]-0.002]
# 相邻面法线夹角(平滑度): 用面积加权法线一致性
norms=np.array([np.array(f.normal[:]) for f in faces])
# 法线y分布(应都朝-Y)
ny=norms[:,1]
print(f"碗内面 {len(faces)}: 法线y mean={ny.mean():.3f} min={ny.min():.3f} max={ny.max():.3f}")
print(f"  朝外(-Y,ny<-0.2): {(ny<-0.2).sum()}, 朝内(+Y,反): {(ny>0.2).sum()}, 侧向: {(abs(ny)<=0.2).sum()}")
# 法线突变(相邻面夹角>60度的比例) - 用方差近似平滑度
# 计算每个面法线与平均法线的夹角
mn = norms.mean(0); mn/=np.linalg.norm(mn)
cosang = norms@mn
cosang=np.clip(cosang,-1,1)
ang = np.degrees(np.arccos(cosang))
print(f"  法线离散度: mean={ang.mean():.1f}° max={ang.max():.1f}° (>40°=穿插/破面迹象)")
print(f"  >40°的面: {(ang>40).sum()} / {len(faces)}")
