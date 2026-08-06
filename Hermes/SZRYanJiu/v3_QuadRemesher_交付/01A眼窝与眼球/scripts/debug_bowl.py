
import bpy, numpy as np, json
IN = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\models\01_1_eye_socket.blend"
DDFA = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\iris_3ddfa.json"
d = json.load(open(DDFA, encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=IN)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V = V.reshape(nv,3).astype(np.float64)
# 碗剖面: 沿xz归一化半径分环, 看每环的y深度
for side in ("L","R"):
    c3 = np.array(d[side]["center_3d"])
    dx=(V[:,0]-c3[0])/0.013; dz=(V[:,2]-c3[2])/0.009
    r2 = dx*dx+dz*dz
    print(f"=== {side} 碗剖面 (ring: 归一化半径带 -> y深度范围) ===")
    for lo,hi in [(0,0.25),(0.25,0.5),(0.5,0.75),(0.75,1.0),(1.0,1.44)]:
        band = (r2>=lo)&(r2<hi)
        sub = V[band]
        # 只取眼窝内的顶点(y在角膜点后方, 即碗内)
        sub = sub[sub[:,1] > c3[1]-0.001]
        if len(sub):
            print(f"  r[{lo:.2f},{hi:.2f}]: n={len(sub)} y[{sub[:,1].min():.4f},{sub[:,1].max():.4f}] deepest={sub[:,1].max():.4f}")
    # 碗的最大深度
    inner = V[r2<1.0]
    inner = inner[inner[:,1] > c3[1]-0.001]
    print(f"  碗最深 y = {inner[:,1].max():.4f}, 角膜点 y = {c3[1]:.4f}, 碗深={(inner[:,1].max()-c3[1])*1000:.1f}mm")
