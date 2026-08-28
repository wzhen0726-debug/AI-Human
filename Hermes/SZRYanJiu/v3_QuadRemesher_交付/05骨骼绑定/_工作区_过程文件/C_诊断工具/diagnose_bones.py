"""骨骼位置诊断：对比骨骼位置与网格实际解剖学位置"""
import bpy
import sys
import math
from mathutils import Vector

def main():
    body = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'eye' not in o.name.lower():
            body = o
            break

    if body is None:
        print("ERROR: no body mesh")
        return

    # 获取世界空间顶点
    world = body.matrix_world
    verts = [(world @ v.co) for v in body.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    z_min, z_max = min(zs), max(zs)
    H = z_max - z_min
    print(f"模型: H={H:.4f}, Z∈[{z_min:.4f},{z_max:.4f}]")
    print(f"X∈[{min(xs):.4f},{max(xs):.4f}] (臂展={max(xs)-min(xs):.4f})")

    # 分析手臂实际的 Z 分布
    # 找手臂顶点 (|X| > 0.3)
    arm_verts = [v for v in verts if abs(v.x) > 0.3]
    print(f"\n=== 手臂顶点 (|X|>0.3) Z 分布 ===")
    if arm_verts:
        arm_zs = [v.z for v in arm_verts]
        print(f"  手臂顶点数: {len(arm_verts)}")
        print(f"  手臂 Z 范围: [{min(arm_zs):.4f}, {max(arm_zs):.4f}]")
        print(f"  手臂 Z 均值: {sum(arm_zs)/len(arm_zs):.4f}")
        print(f"  手臂 Z 中位: {sorted(arm_zs)[len(arm_zs)//2]:.4f}")

    # 找手腕位置: 扫描 X，看截面顶点数和 Z 中心
    print(f"\n=== 手臂截面分析 (从肩到指尖) ===")
    print(f"  X位置 | 顶点数 | Z中心 | Z范围")
    for x in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]:
        band = [v for v in verts if x-0.03 <= v.x <= x+0.03]
        if band:
            bz = [v.z for v in band]
            print(f"  {x:.2f} | {len(band):5d} | {sum(bz)/len(bz):.4f} | [{min(bz):.3f},{max(bz):.3f}]")

    # 找腿部: 左右腿的 X 中心随 Z 变化
    print(f"\n=== 腿部截面分析 ===")
    print(f"  Z高度 | 左腿X中心 | 右腿X中心 | 左腿顶点 | 右腿顶点")
    for z_ratio in [0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        z_t = z_min + H * z_ratio
        band = [v for v in verts if z_t - 0.01*H <= v.z <= z_t + 0.01*H]
        left = [v.x for v in band if v.x > 0.03]
        right = [v.x for v in band if v.x < -0.03]
        lc = sum(left)/len(left) if left else 0
        rc = sum(right)/len(right) if right else 0
        print(f"  {z_t:.3f} ({z_ratio*100:4.0f}%) | {lc:.4f} | {rc:.4f} | {len(left):5d} | {len(right):5d}")

    # 躯干宽度曲线 (X span)
    print(f"\n=== 躯干 X 跨距曲线 (每5%) ===")
    print(f"  Z高度 | X跨距 | 中心X")
    for z_ratio in range(20, 90, 5):
        z_t = z_min + H * z_ratio / 100
        band = [v for v in verts if z_t - 0.01*H <= v.z <= z_t + 0.01*H]
        if band:
            bx = [v.x for v in band]
            span = max(bx) - min(bx)
            cx = sum(bx)/len(bx)
            print(f"  {z_t:.3f} ({z_ratio:3d}%) | {span:.4f} | {cx:.4f}")

if __name__ == "__main__":
    main()
