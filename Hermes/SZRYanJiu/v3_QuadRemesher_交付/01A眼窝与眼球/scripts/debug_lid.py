
import bpy, numpy as np, json
# 看原始高模(未开孔)在眼区的上下睑皮肤分布
REPAIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\01_highpoly_repair.blend"
SOCKET = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
d = json.load(open(DDFA, encoding="utf-8"))
def load_verts(p):
    bpy.ops.wm.open_mainfile(filepath=p)
    obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
    nv = len(obj.data.vertices)
    V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V)
    return V.reshape(nv,3).astype(np.float64)
c3 = np.array(d["L"]["center_3d"])
RX, RZ = 0.013, 0.009
for name, path in [("原始", REPAIR), ("开孔后", SOCKET)]:
    V = load_verts(path)
    dx=(V[:,0]-c3[0])/RX; dz=(V[:,2]-c3[2])/RZ
    r2 = dx*dx+dz*dz
    # 上下睑区: 归一化z超出1.0(椭圆外) 但在1.5内, x在椭圆内
    upper = (r2>=1.0)&(r2<2.25)&(dz>0)&(np.abs(dx)<1.0)
    lower = (r2>=1.0)&(r2<2.25)&(dz<0)&(np.abs(dx)<1.0)
    for lbl, m in [("上睑", upper), ("下睑", lower)]:
        sub = V[m]
        if len(sub):
            print(f"{name} {lbl}: n={len(sub)} y最前={sub[:,1].min():.4f} z范围[{sub[:,2].min():.4f},{sub[:,2].max():.4f}]")
        else:
            print(f"{name} {lbl}: n=0 (皮肤被删光了)")
