import bpy, os, sys, math
from mathutils import Vector, Matrix
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
GLB_PATH = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\AI生成高模\02_tripoTpose\raw_model.glb"
MH_BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\Metahuman_Low_01.blend"
OUT_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_v4.blend")

print("="*60)
print("包裹v4: 先旋转手臂→T-pose, 再Shrinkwrap躯干")
print("="*60)

# 1. 导入Tripo
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
tripo = [o for o in bpy.data.objects if o.type=='MESH'][0]
tripo.name = "Tripo"
bpy.context.view_layer.objects.active = tripo
tripo.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for ax in ['X','Z','Y']:
    tripo.matrix_basis = Matrix.Rotation(math.radians(-90),4,ax) @ tripo.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
zs = [v.co.z for v in tripo.data.vertices]
sc = 1.8/(max(zs)-min(zs))
tripo.scale = (sc,sc,sc)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
xs=[v.co.x for v in tripo.data.vertices]; ys=[v.co.y for v in tripo.data.vertices]; zs=[v.co.z for v in tripo.data.vertices]
tripo.location = (-(min(xs)+max(xs))/2, -(min(ys)+max(ys))/2, -min(zs))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print(f"Tripo: {len(tripo.data.vertices)} verts")

# 2. 导入MetaHuman Body
bpy.ops.wm.append(filepath=os.path.join(MH_BLEND,"Object","NewMetaHumanCharacter_Body"), directory=os.path.join(MH_BLEND,"Object"), filename="NewMetaHumanCharacter_Body")
mh = bpy.data.objects.get("NewMetaHumanCharacter_Body")
for v in mh.data.vertices: v.co *= 0.01
bpy.context.view_layer.update()
mh.matrix_basis = Matrix.Rotation(math.radians(-90),4,'Z') @ mh.matrix_basis
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
zs=[v.co.z for v in mh.data.vertices]; mh_h=max(zs)-min(zs)
mh.scale=(1.8/mh_h,)*3
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
xs=[v.co.x for v in mh.data.vertices]; ys=[v.co.y for v in mh.data.vertices]; zs=[v.co.z for v in mh.data.vertices]
mh.location=(-(min(xs)+max(xs))/2, -(min(ys)+max(ys))/2, -min(zs))
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print(f"MetaHuman: {len(mh.data.vertices)} verts")

xs=[v.co.x for v in mh.data.vertices]; ys=[v.co.y for v in mh.data.vertices]; zs=[v.co.z for v in mh.data.vertices]
print(f"  MH bbox: X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# 3. 识别手臂顶点并旋转到T-pose
print("\n旋转手臂到T-pose...")
# MetaHuman绕Z-90°后: 原X(肩宽)→Y, 原Y(深度)→-X
# 所以手臂在Y方向，肩膀在±Y
# 用户打点的肩膀坐标是在Tripo坐标系(X=手臂方向)
# 但MetaHuman的手臂在Y方向
# 肩膀位置(在MetaHuman坐标系中): Y≈±0.20
shoulder_L = Vector((0.04, -0.20, 1.50))  # 左肩: Y负方向
shoulder_R = Vector((0.04, 0.20, 1.50))   # 右肩: Y正方向

# 分类手臂顶点: 距离肩膀近且|Y|>0.12(远离中线)
arm_L_verts = []
arm_R_verts = []
torso_verts = []
for i, v in enumerate(mh.data.vertices):
    dL = (v.co - shoulder_L).length
    dR = (v.co - shoulder_R).length
    if dL < 0.80 and v.co.y < -0.12:
        arm_L_verts.append(i)
    elif dR < 0.80 and v.co.y > 0.12:
        arm_R_verts.append(i)
    else:
        torso_verts.append(i)

print(f"  左臂: {len(arm_L_verts)} verts")
print(f"  右臂: {len(arm_R_verts)} verts")
print(f"  躯干: {len(torso_verts)} verts")

# 旋转左臂: 手臂在-Y方向(下垂), 需要旋转到-X方向(水平向外)
# 绕X轴旋转: y→-z, z→y (顺时针看X轴)
# 但需要手臂从Y方向转到X方向
# 绕X轴旋转-90°: y→z, z→-y → 手臂从-Y转到-Z(向下), 不对
# 绕Z轴旋转: x→y, y→-x → 手臂从-Y转到+X, 不对(应该转到-X)
# 绕Z轴旋转-90°: x→-y, y→x → 手臂从-Y转到-X ✓
angle = math.radians(45)

# 左臂: 绕shoulder_L, 绕Z轴-90°使手臂从-Y转到-X
for vi in arm_L_verts:
    v = mh.data.vertices[vi]
    rel = v.co - shoulder_L
    rot = Matrix.Rotation(-angle, 4, 'Z')
    new_rel = rot @ rel
    v.co = shoulder_L + new_rel

# 右臂: 绕shoulder_R, 绕Z轴-90°使手臂从+Y转到+X
for vi in arm_R_verts:
    v = mh.data.vertices[vi]
    rel = v.co - shoulder_R
    rot = Matrix.Rotation(-angle, 4, 'Z')
    new_rel = rot @ rel
    v.co = shoulder_R + new_rel

mh.data.update()
xs=[v.co.x for v in mh.data.vertices]; ys=[v.co.y for v in mh.data.vertices]; zs=[v.co.z for v in mh.data.vertices]
print(f"  旋转后MH bbox: X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")

# 4. 创建躯干顶点组, Shrinkwrap只影响躯干
print("\nShrinkwrap躯干...")
vg = mh.vertex_groups.new(name="Torso")
# Shrinkwrap顶点组: 权重1=受影响, 0=不受影响
# torso_verts权重1, arm_verts权重0
vg.add(torso_verts, 1.0, 'REPLACE')
vg.add(arm_L_verts, 0.0, 'REPLACE')
vg.add(arm_R_verts, 0.0, 'REPLACE')

bpy.context.view_layer.objects.active = mh
mh.select_set(True)
sw = mh.modifiers.new(name="SW", type='SHRINKWRAP')
sw.target = tripo
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.wrap_mode = 'ON_SURFACE'
sw.vertex_group = "Torso"
try:
    sw.use_invert_vertex_group = False
except:
    pass

bpy.ops.object.modifier_apply(modifier="SW")

# 5. 第二轮Shrinkwrap: 全身（包括手臂，现在手臂已经在T-pose不会被拉到躯干）
print("\n第二轮Shrinkwrap（全身）...")
sw2 = mh.modifiers.new(name="SW2", type='SHRINKWRAP')
sw2.target = tripo
sw2.wrap_method = 'NEAREST_SURFACEPOINT'
sw2.wrap_mode = 'ON_SURFACE'
bpy.ops.object.modifier_apply(modifier="SW2")

# 5. 验证
xs=[v.co.x for v in mh.data.vertices]; ys=[v.co.y for v in mh.data.vertices]; zs=[v.co.z for v in mh.data.vertices]
print(f"\n包裹后MH bbox: X[{min(xs):.2f},{max(xs):.2f}] Y[{min(ys):.2f},{max(ys):.2f}] Z[{min(zs):.2f},{max(zs):.2f}]")
x_span = max(xs)-min(xs)
print(f"X span: {x_span:.3f} (之前0.26=变形, 正常应>1.0)")

# 精度统计
tripo_verts = [tripo.matrix_world @ v.co for v in tripo.data.vertices]
tripo_faces = [list(p.vertices) for p in tripo.data.polygons]
tripo_bvh = BVHTree.FromPolygons(tripo_verts, tripo_faces)
distances = []
for v in mh.data.vertices:
    wp = mh.matrix_world @ v.co
    n, _, _, _ = tripo_bvh.find_nearest(wp)
    if n: distances.append((wp-n).length)
distances = np.array(distances)
print(f"精度: 平均{np.mean(distances)*1000:.2f}mm, <2mm {np.mean(distances<0.002)*100:.1f}%, 最大{np.max(distances)*1000:.2f}mm")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n保存: {OUT_BLEND}")
print("DONE")
