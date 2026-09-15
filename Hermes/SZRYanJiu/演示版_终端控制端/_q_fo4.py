import bpy, os, json, numpy as np, bmesh, sys
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
F=sys.argv[-1] if sys.argv[-1].endswith(".blend") else os.path.join(D,"01a眼窝眼球","输出","01_1_eye_socket.blend")
bpy.ops.wm.open_mainfile(filepath=F)
print("文件:", os.path.basename(F), "| 手描json keys:", list(J.keys())[:6])
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
bm=bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
def getpoly(side):
    # 兼容几种 json 结构
    if side in J and "rim_3d" in J[side]:
        v=J[side]["rim_3d"]
        return np.array([[float(p[0]),float(p[2])] for p in v])   # 取 XZ
    return None
for side in ("L","R"):
    P=getpoly(side)
    if P is None:
        print(f"  {side}: json 里没找到该侧轮廓"); continue
    bins=[(0.0,0.0005,"rim±0.5mm"),(0.0005,0.0015,"0.5~1.5"),(0.0015,0.003,"1.5~3"),(0.003,0.008,"3~8")]
    out=[]
    for lo,hi,nm in bins:
        cnt=0;back=0
        for f in bm.faces:
            c=f.calc_center_median()
            if abs(c.y-(-0.106))>0.06: continue
            dmin=np.sqrt((P[:,0]-c.x)**2+(P[:,1]-c.z)**2).min()
            if not (lo<=dmin<hi): continue
            cnt+=1
            if f.normal.y>0.0: back+=1
        out.append(f"{nm}: {back}/{cnt}")
    print(f"  {side} 红色数: " + " | ".join(out))
bm.free()
