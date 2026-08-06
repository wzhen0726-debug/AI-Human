
import bpy, numpy as np, json
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
d = json.load(open(DDFA, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=SOCKET)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V=V.reshape(nv,3).astype(np.float64)
c3 = np.array(d["L"]["center_3d"]); RX,RZ=0.013,0.009
dx=(V[:,0]-c3[0])/RX; dz=(V[:,2]-c3[2])/RZ; r2=dx*dx+dz*dz
# 睑缘 = 开孔椭圆边界上的皮肤顶点(r2在1.0~1.2). 分上下.
edge = (r2>=1.0)&(r2<1.25)
up = V[edge & (dz>0.3)]   # 上睑缘
lo = V[edge & (dz<-0.3)]  # 下睑缘
print("=== 左眼 睑缘(开孔边缘皮肤) ===")
for lbl,m in [("上睑缘",up),("下睑缘",lo)]:
    if len(m): print(f"  {lbl}: n={len(m)} y范围[{m[:,1].min():.4f},{m[:,1].max():.4f}] 最前={m[:,1].min():.4f} 最后={m[:,1].max():.4f}")
# 角膜前极当前-0.129. 要被睑缘遮住, 球前极y应 > 睑缘最前y(即更靠后+Y)
print(f"当前球前极y=-0.1290")
print(f"上睑缘最前={up[:,1].min():.4f}: 球前极要比它靠后(>此值)才被上睑盖住")
