"""诊断: 从输入高模提取真实眼睑边缘(几何急剧弯曲环), 与3DDFA轮廓对比.

原理: 眼窝开口处, 上/下眼睑在"皮肤平面"与"眼裂平面"之间有急剧的几何弯曲(fold).
对眼区每个顶点, 看其局部邻域法线变化/曲率, 弯曲最大的环即眼睑边缘.
简化做法: 眼睑边缘 = 眼裂周围沿径向扫描, 找Y(深度)梯度突变的位置.

更简单可靠: 眼睑是上下两片皮肤在眼裂处相遇形成的"折痕".
在原始高模上, 眼裂是一条狭长带, 上下眼睑皮肤几乎贴合.
=> 用X-Z平面: 对每条水平线(z=const), 在眼区找y最大(最凹)和眼睑皮肤转折.
这里用最直接的: 找眼区内 y(深度) 沿 z 方向变化率最大的两个环(上缘/下缘折痕),
以及沿 x 方向变化率最大的内外眼角点.
"""
import bpy, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    mesh = obj.data
    mesh.calc_loop_triangles()

    result = {}
    for side, ic in [('L', IRIS_L), ('R', IRIS_R)]:
        center = np.array(ic)
        # 收集眼区顶点 (距虹膜中心 xz半径20mm, y在脸前)
        verts = []
        for v in mesh.vertices:
            co = np.array(v.co)
            dx = co[0]-center[0]; dz = co[2]-center[2]
            r = math.sqrt(dx*dx+dz*dz)
            if r < 0.020 and co[1] < center[1]+0.005:
                verts.append((co, r, dx, dz))
        verts = np.array([v[0] for v in verts])
        print(f"{side}: {len(verts)} verts in eye region")

        # 网格化: 把眼区按 (x,z) 分格, 每格取 y 最小(最前)点 —— 脸表面
        # 眼睑折痕检测: 沿z扫描, 对每列x, 找 y 沿 z 的二阶差分最大处(折痕)
        xs = verts[:,0]; zs = verts[:,2]; ys = verts[:,1]
        # 极坐标展开: 以虹膜中心为原点, 角度θ∈[0,2π), 半径r
        thetas = np.arctan2(zs-center[2], xs-center[0])
        rs = np.sqrt((xs-center[0])**2 + (zs-center[2])**2)
        # 对每个角度bin, 找 rs-y 关系中 y 突增(向后凹)的半径 = 眼睑折痕
        n_bins = 72
        rim_pts = []
        for b in range(n_bins):
            a0 = -math.pi + 2*math.pi*b/n_bins
            a1 = -math.pi + 2*math.pi*(b+1)/n_bins
            m = (thetas >= a0) & (thetas < a1)
            if m.sum() < 5: continue
            br = rs[m]; by = ys[m]
            # 按r排序, 计算 y 沿 r 的梯度, 找梯度最大点(皮肤开始向后折入眼裂处)
            order = np.argsort(br)
            br, by = br[order], by[order]
            if len(br) < 5: continue
            # 平滑梯度
            gy = np.gradient(by, br)
            # 折痕 = 梯度最大处(向+Y即头内方向弯)
            k = int(np.argmax(gy))
            # 取该角度上折痕点
            ang = (a0+a1)/2
            rim_pts.append((center[0] + br[k]*math.cos(ang),
                            by[k],
                            center[2] + br[k]*math.sin(ang)))
        rim_pts = np.array(rim_pts)

        # 与3DDFA轮廓对比
        d = json.load(open(EYELID_CONTOUR_JSON, encoding="utf-8"))
        ddfa = np.array([[r[0], r[2]] for r in d[side]["rim_3d"] if r is not None])

        geo_x = rim_pts[:,0]; geo_z = rim_pts[:,2]
        dx_ = ddfa[:,0]; dz_ = ddfa[:,1]
        print(f"{side} 几何眼睑边缘: x[{geo_x.min():.4f},{geo_x.max():.4f}] 宽{(geo_x.max()-geo_x.min())*1000:.1f}mm  "
              f"z[{geo_z.min():.4f},{geo_z.max():.4f}] 高{(geo_z.max()-geo_z.min())*1000:.1f}mm")
        print(f"{side} 3DDFA轮廓:   x[{dx_.min():.4f},{dx_.max():.4f}] 宽{(dx_.max()-dx_.min())*1000:.1f}mm  "
              f"z[{dz_.min():.4f},{dz_.max():.4f}] 高{(dz_.max()-dz_.min())*1000:.1f}mm")

        # 上下缘/内外眼角分别对比
        for nm, gi, di in [
            ("上缘z", geo_z.max(), dz_.max()),
            ("下缘z", geo_z.min(), dz_.min()),
            ("外眼角x", geo_x.max() if side=='L' else geo_x.min(),
                      dx_.max() if side=='L' else dx_.min()),
            ("内眼角x", geo_x.min() if side=='L' else geo_x.max(),
                      dx_.min() if side=='L' else dx_.max()),
        ]:
            print(f"  {nm}: 几何={gi:.4f} 3DDFA={di:.4f} 差={(gi-di)*1000:+.1f}mm")

        result[side] = {
            "rim_3d_geometry": [list(map(float, p)) for p in rim_pts],
            "width_mm": float((geo_x.max()-geo_x.min())*1000),
            "height_mm": float((geo_z.max()-geo_z.min())*1000),
        }

    out = os.path.join(os.path.dirname(EYELID_CONTOUR_JSON), "eyelid_contour_geometry.json")
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", out)

main()
