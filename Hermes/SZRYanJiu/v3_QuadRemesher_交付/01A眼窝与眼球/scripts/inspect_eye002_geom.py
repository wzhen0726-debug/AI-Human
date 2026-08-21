"""检查眼睛模型002几何: bbox/半径/朝向/巩膜球心."""
import bpy, os
from mathutils import Vector
import math

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002\Eye.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

for o in bpy.data.objects:
    if o.type != 'MESH': continue
    V = [o.matrix_world @ v.co for v in o.data.vertices]
    mn = Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V)))
    mx = Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V)))
    c = (mn + mx) / 2
    print(f"{o.name}: bbox {tuple(round(x,4) for x in mn)} ~ {tuple(round(x,4) for x in mx)}")
    print(f"  size={tuple(round((mx-mn)[i],4) for i in range(3))} center={tuple(round(x,4) for x in c)}")

# 巩膜球拟合: 取巩膜顶点算到中心的平均距离(球半径)
scl = bpy.data.objects.get("Eye_Sclera")
if scl:
    V = [scl.matrix_world @ v.co for v in scl.data.vertices]
    c = sum(V, Vector((0,0,0))) / len(V)
    rs = sorted((v-c).length for v in V)
    print(f"\nEye_Sclera 球心={tuple(round(x,4) for x in c)}")
    print(f"  半径: min={rs[0]*1000:.2f}mm median={rs[len(rs)//2]*1000:.2f}mm max={rs[-1]*1000:.2f}mm")

# 虹膜朝向: 虹膜面平均法线方向
iri = bpy.data.objects.get("Eye_Iris")
if iri:
    import bmesh
    bm = bmesh.new(); bm.from_mesh(iri.data); bm.normal_update()
    n_avg = sum((f.normal for f in bm.faces), Vector((0,0,0)))
    n_avg.normalize()
    print(f"\nEye_Iris 平均法线={tuple(round(x,3) for x in n_avg)}")
    bm.free()
