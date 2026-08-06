
import bpy, numpy as np
from mathutils import Vector
# 在眼球中心高度(z=1.6711)水平切片, 提取头表面与眼球的截面轮廓
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_2_eyeball_placed.blend"
bpy.ops.wm.open_mainfile(filepath=IN)
zc = 1.6711; tol = 0.002
# 头表面在z=zc处的最前点(y最小) 沿x分布
head = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(head.data.vertices)
V = np.empty(nv*3, dtype=np.float32); head.data.vertices.foreach_get("co", V); V=V.reshape(nv,3).astype(np.float64)
band = np.abs(V[:,2]-zc) < tol
sub = V[band]
# 左眼区 x in [-0.06,-0.01]
eye = sub[(sub[:,0]>-0.06)&(sub[:,0]<-0.01)]
print(f"头表面在z={zc} 左眼区: n={len(eye)}")
if len(eye):
    # 最靠前的皮肤点
    i = np.argmin(eye[:,1])
    print(f"  最前皮肤点: x={eye[i,0]:.4f} y={eye[i,1]:.4f}")
# 眼球: GLB眼球mesh
eyeL = [o for o in bpy.data.objects if o.type=='MESH' and 'Eye' in o.name and o.location.x<0][0]
ec = np.array(eyeL.location[:]); R=0.0145
print(f"眼球L: center={np.round(ec,4)} 在z={zc}处球前极y={ec[1]-R:.4f}")
print(f"=> 球前极({'{:.4f}'.format(ec[1]-R)}) vs 皮肤最前({'{:.4f}'.format(eye[i,1])}): 差={((ec[1]-R)-eye[i,1])*1000:+.2f}mm (负=球在皮肤前=凸出)")
