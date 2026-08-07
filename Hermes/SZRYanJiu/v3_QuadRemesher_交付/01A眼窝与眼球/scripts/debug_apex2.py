
import bpy, numpy as np, json
REPAIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\01_highpoly_repair.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour.json"
bpy.ops.wm.open_mainfile(filepath=REPAIR)
d = json.load(open(DDFA, encoding="utf-8"))
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv=len(obj.data.vertices); V=np.empty(nv*3,dtype=np.float32); obj.data.vertices.foreach_get("co",V); V=V.reshape(nv,3).astype(np.float64)
# 眼球角膜该在: 原始眼睑轮廓内, 眼睑皮肤的最凸点(apex)就是闭眼时眼球顶着眼睑的位置
for side in ("L","R"):
    rim=[r for r in d[side]["rim_3d"] if r]
    c=np.array(rim).mean(0)
    # 轮廓内的顶点(用眼形椭圆近似: 宽26.8高9.7 -> rx13.4 rz4.85)
    dx=(V[:,0]-c[0])/0.0134; dz=(V[:,2]-c[2])/0.00485
    ine=(dx*dx+dz*dz)<1.0
    sub=V[ine]
    apex_y = sub[:,1].min()  # 最前(最凸)眼睑皮肤
    p50 = np.percentile(sub[:,1],50)
    print(f"{side}: 眼睑轮廓内 apex_y={apex_y:.4f} (眼球角膜前极应≈此值) median_y={p50:.4f}")
    print(f"   => 建议球心y = apex_y + R = {apex_y+0.0145:.4f} (当前-0.1142)")
