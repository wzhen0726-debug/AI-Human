# 造"不同尺寸/不同头型"的测试输入: 网格 + 两份 json 同步缩放(sx,sy,sz)
import bpy, json, os
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
T=os.path.join(D,"_通用性测试")
sx, sy, sz = 1.15, 1.15, 1.06      # 头更大、更宽扁; 眼间距/眼高随之变化
bpy.ops.wm.open_mainfile(filepath=os.path.join(D,"01高模修复","输出","01_highpoly_repair.blend"))
n=0
for o in bpy.data.objects:
    if o.type!='MESH': continue
    for v in o.data.vertices:
        v.co.x*=sx; v.co.y*=sy; v.co.z*=sz
    o.data.update(); n+=1
out=os.path.join(T,"scaled_head.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("网格已缩放:", out, "对象", n)
def sc_pt(p): return [p[0]*sx, p[1]*sy, p[2]*sz]
for src, dst, keys in (
    (os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),
     os.path.join(T,"eyelid_contour_scaled.json"), ("rim_3d","center")),
    (os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","iris_3ddfa.json"),
     os.path.join(T,"iris_3ddfa_scaled.json"), ("center_3d","center")),
):
    d=json.load(open(src,encoding="utf-8"))
    for side in ("L","R"):
        if side not in d: continue
        for k in keys:
            if k in d[side] and isinstance(d[side][k], list):
                if k=="rim_3d": d[side][k]=[sc_pt(p) for p in d[side][k]]
                else: d[side][k]=sc_pt(d[side][k])
        if "width_mm" in d[side]: d[side]["width_mm"]*=sx
        if "height_mm" in d[side]: d[side]["height_mm"]*=sz
    json.dump(d, open(dst,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print("json 已缩放:", dst)
