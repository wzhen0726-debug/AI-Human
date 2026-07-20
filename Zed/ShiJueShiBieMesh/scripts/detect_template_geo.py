"""
在模板上用几何方法检测特征点顶点索引
模板几何干净，启发式检测应该准确
"""
import bpy, numpy as np, json

TEMPLATE = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\MetaHuman_head\MH_Head_01.obj"
OUTPUT = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final\template_landmarks.json"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath=TEMPLATE)
template_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH': template_obj = obj; break

# 模板原始坐标（local space）
coords = np.array([v.co for v in template_obj.data.vertices])
n_verts = len(coords)
x_min, x_max = coords[:,0].min(), coords[:,0].max()
y_min, y_max = coords[:,1].min(), coords[:,1].max()
z_min, z_max = coords[:,2].min(), coords[:,2].max()
print(f"BBox: X[{x_min:.3f},{x_max:.3f}] Y[{y_min:.3f},{y_max:.3f}] Z[{z_min:.3f},{z_max:.3f}]")
yr, zr = y_max-y_min, z_max-z_min

landmarks = {}

# 鼻尖: Z 最大
fwd = coords[coords[:,2] > z_min + 0.7*zr]
ni = np.argmax(fwd[:,2])
landmarks['nose_tip'] = int(np.where(np.all(np.abs(coords-fwd[ni])<0.001,axis=1))[0][0])

# 左右眼角: 眼区(Y中上部) Z 最小值（最凹陷）
eye_lo, eye_hi = y_min+0.55*yr, y_min+0.75*yr
for side, sign in [('left_eye', -1), ('right_eye', 1)]:
    mask = (coords[:,1]>eye_lo)&(coords[:,1]<eye_hi)&(coords[:,2]>z_min+0.5*zr)&(sign*coords[:,0]>0.01)
    if np.any(mask):
        idx = np.where(mask)[0]
        landmarks[f'{side}_inner'] = int(idx[np.argmax(sign*coords[idx,0])])  # X最内
        landmarks[f'{side}_outer'] = int(idx[np.argmin(sign*coords[idx,0])])  # X最外

# 嘴角: 嘴区(Y中下部) X 极值
mouth_y = y_min + 0.32*yr
for side, sign in [('left_mouth', -1), ('right_mouth', 1)]:
    mask = (np.abs(coords[:,1]-mouth_y)<0.04*yr)&(coords[:,2]>z_min+0.5*zr)&(sign*coords[:,0]>0.005)
    if np.any(mask):
        idx = np.where(mask)[0]
        landmarks[f'{side}_corner'] = int(idx[np.argmax(sign*coords[idx,0])])

# 下巴: Y 最小 + Z 大
mask = (coords[:,1] < y_min+0.1*yr) & (coords[:,2] > z_min+0.3*zr)
if np.any(mask):
    idx = np.where(mask)[0]
    landmarks['chin'] = int(idx[np.argmin(coords[idx,1])])

# 眉心: Y在两眼中部, X≈0
mask = (np.abs(coords[:,1]-(y_min+0.68*yr))<0.03*yr)&(np.abs(coords[:,0])<0.005)&(coords[:,2]>z_min+0.5*zr)
if np.any(mask):
    idx = np.where(mask)[0]
    landmarks['nose_bridge'] = int(idx[np.argmax(coords[idx,2])])

# 额头
mask = (coords[:,1]>y_min+0.85*yr)&(np.abs(coords[:,0])<0.005)
if np.any(mask):
    idx = np.where(mask)[0]
    landmarks['forehead'] = int(idx[np.argmax(coords[idx,2])])

# 左右眉弓
for side, sign in [('left_brow', -1), ('right_brow', 1)]:
    mask = (np.abs(coords[:,1]-(y_min+0.7*yr))<0.03*yr)&(sign*coords[:,0]>0.02)&(coords[:,2]>z_min+0.4*zr)
    if np.any(mask):
        idx = np.where(mask)[0]
        landmarks[f'{side}'] = int(idx[np.argmax(coords[idx,2])])

print(f"检测到 {len(landmarks)} 个特征点:")
for name, idx in landmarks.items():
    print(f"  {name}: vertex={idx}, pos=({coords[idx,0]:.4f},{coords[idx,1]:.4f},{coords[idx,2]:.4f})")

with open(OUTPUT, 'w') as f:
    json.dump(landmarks, f, indent=2)
print(f"\n保存到: {OUTPUT}")
print(f"\n请在 Blender 中打开 MH_Head_01.obj，逐个检查这些顶点是否在正确位置。")
print(f"如有不对，修改 JSON 文件中的 vertex_index 值即可。")