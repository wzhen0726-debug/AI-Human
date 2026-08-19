"""v39 综合诊断: 纹理错乱(棋盘格) + 眼窝边缘几何 + 交缝精度.
1. 纹理: 检查眼窝区UV分布, 是否棋盘格(UV重复/拉伸)
2. 边缘: 检查ring0锯齿(相邻顶点半径跳变), 倒角带与皮肤过渡
3. 交缝: 检查开口轮廓与3DDFA眼裂的偏差
"""
import bpy, bmesh, json, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = obj.data

def load_3ddfa():
    with open(DDFA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return Vector(d["L"]["center_3d"]), Vector(d["R"]["center_3d"])
cL, cR = load_3ddfa()

bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()

print("=== 1. 纹理诊断(UV分析) ===")
uv_layer = bm.loops.layers.uv.active
if uv_layer:
    for side, center in [("L", cL), ("R", cR)]:
        # 收集眼窝区所有面的UV
        bowl_uvs = []
        skin_uvs = []
        for f in bm.faces:
            fc = f.calc_center_median()
            dxz = math.sqrt((fc.x-center.x)**2 + (fc.z-center.z)**2)
            if center.y < fc.y < center.y + 0.02 and dxz < 0.021:
                for loop in f.loops:
                    bowl_uvs.append(loop[uv_layer].uv)
            elif fc.y < center.y and dxz < 0.025:
                for loop in f.loops:
                    skin_uvs.append(loop[uv_layer].uv)
        if bowl_uvs:
            us = [uv.x for uv in bowl_uvs]; vs = [uv.y for uv in bowl_uvs]
            print(f"  {side}碗面 UV: {len(bowl_uvs)} loops")
            print(f"    u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")
            print(f"    范围: {max(us)-min(us):.4f} x {max(vs)-min(vs):.4f}")
            # 检查是否均匀(avg_uv)
            avg_u = sum(us)/len(us); avg_v = sum(vs)/len(vs)
            same = sum(1 for uv in bowl_uvs if abs(uv.x-avg_u)<0.001 and abs(uv.y-avg_v)<0.001)
            print(f"    均匀UV占比: {same}/{len(bowl_uvs)} ({same/len(bowl_uvs)*100:.1f}%)")
        if skin_uvs:
            us = [uv.x for uv in skin_uvs]; vs = [uv.y for uv in skin_uvs]
            print(f"  {side}皮肤 UV: {len(skin_uvs)} loops, u=[{min(us):.4f},{max(us):.4f}] v=[{min(vs):.4f},{max(vs):.4f}]")

print("\n=== 2. 眼窝边缘诊断 ===")
for side, center in [("L", cL), ("R", cR)]:
    # 找ring0附近顶点(皮肤与倒角带交界)
    rim_verts = []
    for v in bm.verts:
        dxz = math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2)
        if 0.015 < dxz < 0.019 and abs(v.co.y - center.y) < 0.005:
            rim_verts.append(v)
    if rim_verts:
        rim_verts.sort(key=lambda v: math.atan2(v.co.z-center.z, v.co.x-center.x))
        radii = [math.sqrt((v.co.x-center.x)**2 + (v.co.z-center.z)**2) for v in rim_verts]
        jumps = [abs(radii[(i+1)%len(radii)] - radii[i]) for i in range(len(radii))]
        print(f"  {side} rim顶点: {len(rim_verts)}个")
        print(f"    径向半径: [{min(radii)*1000:.2f},{max(radii)*1000:.2f}]mm")
        print(f"    相邻跳变: avg={sum(jumps)/len(jumps)*1000:.2f}mm max={max(jumps)*1000:.2f}mm")
        # 大跳变位置
        big_jumps = [(i, jumps[i]*1000) for i in range(len(jumps)) if jumps[i] > 0.001]
        if big_jumps:
            print(f"    大跳变(>1mm): {len(big_jumps)}处")
            for idx, jmp in big_jumps[:5]:
                print(f"      位置{idx}: {jmp:.2f}mm")

print("\n=== 3. 交缝精度诊断 ===")
# 检查开口轮廓与3DDFA眼裂的匹配
for side, center in [("L", cL), ("R", cR)]:
    poly = load_eyelid_contour(side)
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    w = max(xs) - min(xs); h = max(zs) - min(zs)
    print(f"  {side} 轮廓: 宽{w*1000:.1f}mm 高{h*1000:.1f}mm")
    # 找眼窝开口实际边界(开放边)
    open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    eye_open = [e for e in open_edges
                if math.sqrt(((e.verts[0].co.x+e.verts[1].co.x)/2-center.x)**2 +
                            ((e.verts[0].co.z+e.verts[1].co.z)/2-center.z)**2) < 0.025]
    if eye_open:
        xs_e = [(e.verts[0].co.x+e.verts[1].co.x)/2 for e in eye_open]
        zs_e = [(e.verts[0].co.z+e.verts[1].co.z)/2 for e in eye_open]
        print(f"    实际开口: 宽{(max(xs_e)-min(xs_e))*1000:.1f}mm 高{(max(zs_e)-min(zs_e))*1000:.1f}mm")
        print(f"    开放边数: {len(eye_open)}")

bm.free()
print("\n=== 诊断完成 ===")
