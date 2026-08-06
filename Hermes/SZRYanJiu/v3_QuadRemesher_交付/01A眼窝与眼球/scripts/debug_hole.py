
import bpy, numpy as np, json
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
RX, RZ = 0.013, 0.009
d = json.load(open(DDFA, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=IN)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V = V.reshape(nv,3).astype(np.float64)
for side in ("L","R"):
    c = np.array(d[side]["center_3d"])
    dx=(V[:,0]-c[0])/RX; dz=(V[:,2]-c[2])/RZ
    ine = dx*dx+dz*dz <= 1.0
    sub = V[ine]
    print(f"=== {side}: 椭圆内剩余顶点 {len(sub)} ===")
    if len(sub):
        ys = sub[:,1]
        print(f"  y: min={ys.min():.4f} max={ys.max():.4f} mean={ys.mean():.4f}")
        # 比角膜点更靠前的顶点(应该被删的)
        n_front = int((ys < c[1]).sum())
        print(f"  y < cornea_y({c[1]:.4f}) 的残留顶点: {n_front}  <- 这些本该被删掉")
        # 它们在哪
        fr = sub[ys < c[1]]
        if len(fr):
            print(f"    残留前部顶点 z范围: [{fr[:,2].min():.4f},{fr[:,2].max():.4f}]  x范围: [{fr[:,0].min():.4f},{fr[:,0].max():.4f}]")
