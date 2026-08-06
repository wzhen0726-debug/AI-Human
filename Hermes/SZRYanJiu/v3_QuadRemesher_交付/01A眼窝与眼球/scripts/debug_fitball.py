
import bpy, numpy as np, json
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
d = json.load(open(DDFA, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=IN)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V = V.reshape(nv,3).astype(np.float64)
R = 0.0145
for side in ("L","R"):
    fit = d[side]["fitted_sphere"]["center"]
    c3 = np.array(d[side]["center_3d"])
    # 用拟合球心x/z, 但r=14.5mm的GLB眼球; y用拟合球心y
    bc = np.array([fit[0], fit[1], c3[2]])  # z用3DDFA的(更准)
    print(f"=== {side} 拟合球心方案 ball_center={np.round(bc,4)} ===")
    print(f"  角膜前极 y={bc[1]-R:.4f} (原始眼睑apex≈-0.129, 前极应≈apex让眼睑贴合)")
    # 穿透: 头表面顶点(开口附近)有多少在球内
    dx=(V[:,0]-c3[0])/0.013; dz=(V[:,2]-c3[2])/0.009
    ine = dx*dx+dz*dz <= 1.44
    sub = V[ine]
    dist = np.linalg.norm(sub-bc, axis=1)
    inside = dist < R
    print(f"  开口区顶点 {len(sub)}, 在球内 {inside.sum()}")
    if inside.sum():
        iv = sub[inside]
        pen = R - dist[inside]
        print(f"  穿透 max={pen.max()*1000:.2f}mm, 穿透顶点y范围[{iv[:,1].min():.4f},{iv[:,1].max():.4f}]")
        # 穿透的是头内部顶点(y很大)还是表面? 头内部顶点是后脑壳内壁,不算穿帮
        surf = iv[iv[:,1] < c3[1]]  # 比角膜点靠前的才算表面穿帮
        print(f"  其中比角膜点靠前的(真表面穿帮): {len(surf)}")
