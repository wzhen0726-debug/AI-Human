"""diagnose_eyelid_uv: 定位下眼睑UV错乱面
症状: 左右眼下眼睑对称深棕色锯齿斑块 = UV采样到了贴图深色区(眉毛/发际线)
诊断: 1) 找下眼睑区域的面片(眼窝开口下缘、rim外)
      2) 检查这些面的UV位置是否异常(落在贴图深色区)
      3) 对比正常皮肤面的UV
"""
import bpy, bmesh, os, sys, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]

with open(DDFA_JSON, encoding="utf-8") as f:
    d = json.load(f)
cL = Vector(d["L"]["center_3d"]); cR = Vector(d["R"]["center_3d"])

bm = bmesh.new(); bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active

# 眼窝下缘区域: 眼裂下方 dz<0(下侧), dxz在rim附近(6-16mm)
# 用户截图显示斑块在下眼睑, 即z<center.z
print("=== 眼窝下缘面片UV检查 ===")
for side, center in [("L", cL), ("R", cR)]:
    bad_faces = []   # UV异常的面
    good_faces = []  # 正常面
    for f in bm.faces:
        fc = f.calc_center_median()
        dx = fc.x - center.x; dz = fc.z - center.z
        dxz = math.sqrt(dx*dx + dz*dz)
        # 下眼睑区域: 下方(dz<0), 开口附近(3-18mm), 脸部前缘
        if dz < -0.002 and 0.003 < dxz < 0.018 and fc.y < -0.09:
            # 取该面的UV
            uvs = [l[uv_layer].uv.copy() for l in f.loops]
            avg_u = sum(uv.x for uv in uvs)/len(uvs)
            avg_v = sum(uv.y for uv in uvs)/len(uvs)
            # UV范围(检查是否拉伸)
            u_span = max(uv.x for uv in uvs) - min(uv.x for uv in uvs)
            v_span = max(uv.y for uv in uvs) - min(uv.y for uv in uvs)
            info = (fc.copy(), avg_u, avg_v, u_span*1000, v_span*1000, len(uvs))
            # 判断异常: UV跨度过大(拉伸) 或 UV落在异常位置
            if u_span > 0.05 or v_span > 0.05:  # UV拉伸>5%贴图
                bad_faces.append(('stretch', info))
            else:
                good_faces.append(info)
    
    print(f"\n{side}眼 下眼睑区: 正常面={len(good_faces)} UV拉伸面={len(bad_faces)}")
    if good_faces:
        us = [g[1] for g in good_faces]; vs = [g[2] for g in good_faces]
        print(f"  正常面UV范围: u=[{min(us):.3f},{max(us):.3f}] v=[{min(vs):.3f},{max(vs):.3f}]")
    for kind, info in bad_faces[:8]:
        fc, u, v, us, vs, n = info
        dx = (fc.x-center.x)*1000; dz = (fc.z-center.z)*1000
        print(f"  [{kind}] 位置({dx:+.1f},{dz:+.1f})mm UV=({u:.3f},{v:.3f}) 跨度({us:.1f},{vs:.1f}) ‰贴图 {n}loops")
bm.free()
print("\n诊断完成")
