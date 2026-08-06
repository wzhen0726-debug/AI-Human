
import bpy, numpy as np, json
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
d = json.load(open(DDFA, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=IN)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V = V.reshape(nv,3).astype(np.float64)
# 眼球心(run_eyeball最后放的): L=(-0.0358,-0.0937,1.6711) R=(0.0326,-0.0944,1.6707) r=14.5mm
balls = {"L": np.array([-0.0358,-0.0937,1.6711]), "R": np.array([0.0326,-0.0944,1.6707])}
R = 0.0145
for side in ("L","R"):
    bc = balls[side]
    c3 = np.array(d[side]["center_3d"])
    dx=(V[:,0]-c3[0])/0.013; dz=(V[:,2]-c3[2])/0.009
    ine = dx*dx+dz*dz <= 1.44  # 开口+边缘
    sub = V[ine]
    dist = np.linalg.norm(sub-bc, axis=1)
    inside = dist < R
    print(f"=== {side}: 开口区内顶点 {len(sub)}, 在球内 {inside.sum()} ===")
    if inside.sum():
        pen = R - dist[inside]
        iv = sub[inside]
        print(f"  穿透深度 max={pen.max()*1000:.2f}mm mean={pen.mean()*1000:.2f}mm")
        print(f"  穿透顶点 y范围[{iv[:,1].min():.4f},{iv[:,1].max():.4f}] z范围[{iv[:,2].min():.4f},{iv[:,2].max():.4f}]")
        # 这些穿透顶点是眼睑皮肤(原本很靠前)还是碗面?
        print(f"  穿透顶点里最前的y={iv[:,1].min():.4f} (原始眼睑apex≈-0.129), 最后的y={iv[:,1].max():.4f}")
