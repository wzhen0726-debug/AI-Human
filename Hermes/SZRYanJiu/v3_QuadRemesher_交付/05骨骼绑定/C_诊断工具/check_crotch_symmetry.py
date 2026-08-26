"""检查: 模型真实的胯部(会阴区)是否在中线, 对比用户打的会阴点."""
import bpy
import numpy as np

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\04纹理烘焙\04_bake.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

body = max((o for o in bpy.data.objects if o.type == 'MESH' and 'eye' not in o.name.lower()),
           key=lambda o: len(o.data.vertices))
mw = np.array(body.matrix_world)
vs = np.array([v.co for v in body.data.vertices])
ws = (mw[:3, :3] @ vs.T).T + mw[:3, 3]

# 会阴区域: z在0.70~0.90之间的顶点
band = ws[(ws[:, 2] > 0.70) & (ws[:, 2] < 0.90)]
print(f"会阴带顶点数: {len(band)}")
print(f"  x范围: {band[:,0].min():.3f} ~ {band[:,0].max():.3f}")
print(f"  x中点: {(band[:,0].min()+band[:,0].max())/2:.3f}")
# 找最靠下的顶点(会阴最低点)
low = band[band[:, 2].argmin()]
print(f"  会阴带最低点: ({low[0]:.3f}, {low[1]:.3f}, {low[2]:.3f})")
# 按x对称性: 左右各一半的x均值
print(f"  左侧x均值: {band[band[:,0]<0][:,0].mean():.3f}, 右侧x均值: {band[band[:,0]>0][:,0].mean():.3f}")
print("CROTCH_CHECK_DONE")
