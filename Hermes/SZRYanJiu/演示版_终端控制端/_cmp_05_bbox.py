# -*- coding: utf-8 -*-
"""只读验证: 旧05网格 vs 新04_bake网格 的bbox/尺寸是否一致.
若一致 → 用户手调的17个EMPTY点位世界坐标在新网格上依然准确, 无需重调.
⚠不写任何文件."""
import bpy, os
import numpy as np
D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
P05 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831", "01_AI打点.blend")
BAKE = os.path.join(D, "交付", "04纹理烘焙", "04_bake.blend")

def load_bb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    o = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
    mw = o.matrix_world; me = o.data
    co = np.empty(len(me.vertices)*3); me.vertices.foreach_get("co", co)
    V = co.reshape(-1, 3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)
    return o.name, V, len(me.polygons)

n1, V1, f1 = load_bb(P05)
n2, V2, f2 = load_bb(BAKE)
print(f"旧05网格: '{n1}' 顶点={len(V1):,} 面={f1:,}")
print(f"新04网格: '{n2}' 顶点={len(V2):,} 面={f2:,}")

for tag, V in (("旧05", V1), ("新04", V2)):
    mn, mx = V.min(axis=0), V.max(axis=0)
    print(f"\n{tag} bbox(mm):")
    print(f"  x[{mn[0]*1000:.2f},{mx[0]*1000:.2f}] 宽={np.ptp(V[:,0])*1000:.2f}")
    print(f"  y[{mn[1]*1000:.2f},{mx[1]*1000:.2f}] 深={np.ptp(V[:,1])*1000:.2f}")
    print(f"  z[{mn[2]*1000:.2f},{mx[2]*1000:.2f}] 高={np.ptp(V[:,2])*1000:.2f}")
    print(f"  中心=({V[:,0].mean()*1000:.2f},{V[:,1].mean()*1000:.2f},{V[:,2].mean()*1000:.2f})")

d_min = V2.min(axis=0) - V1.min(axis=0); d_max = V2.max(axis=0) - V1.max(axis=0)
print(f"\nbbox差异(mm): min差={tuple(round(v*1000,3) for v in d_min)}  max差={tuple(round(v*1000,3) for v in d_max)}")
sz1 = np.ptp(V1, axis=0); sz2 = np.ptp(V2, axis=0)
print(f"尺寸差异(mm): {tuple(round(v*1000,3) for v in (sz2-sz1))}  相对={tuple(round(v/s*100,4) for v,s in zip(sz2-sz1, sz1))}%")
print(f"中心偏移(mm): {tuple(round(v*1000,3) for v in (V2.mean(axis=0)-V1.mean(axis=0)))}")

# 逐点最近距离(整体形变量级) — 分块防内存爆
from mathutils.kdtree import KDTree
kd = KDTree(len(V2))
for i, v in enumerate(V2): kd.insert(v, i)
kd.balance()
samp = V1[np.random.RandomState(0).choice(len(V1), min(20000, len(V1)), replace=False)]
ds = np.array([kd.find(v)[2] for v in samp]) * 1000
print(f"\n旧网格采样{len(samp):,}点 → 新网格最近距离: 中位={np.median(ds):.4f} p95={np.percentile(ds,95):.4f} max={ds.max():.4f}mm")
print(f"  (<0.5mm = 同一几何, 仅布线不同 → 点位世界坐标依然有效)")
BB_DONE
