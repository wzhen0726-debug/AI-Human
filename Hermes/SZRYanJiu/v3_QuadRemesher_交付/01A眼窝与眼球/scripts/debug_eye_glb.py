"""debug: 检查eye_01.glb导入后的层级/原点/半径, 找出摆入偏外的根因"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
bpy.ops.import_scene.gltf(filepath=EYE_GLB)
imported = [o for o in bpy.context.selected_objects if o.type == 'MESH']

for o in imported:
    print(f"=== {o.name} ===")
    print(f"  parent: {o.parent.name if o.parent else None}")
    print(f"  location(local): {[round(v,4) for v in o.location]}")
    print(f"  rotation_quat(local): {[round(v,4) for v in o.rotation_quaternion]}")
    mw = o.matrix_world
    print(f"  matrix_world translation: {[round(v,4) for v in mw.translation]}")
    # 顶点局部坐标bbox -> 球心与半径
    V = np.array([v.co[:] for v in o.data.vertices])
    bb_min, bb_max = V.min(0), V.max(0)
    center = (bb_min + bb_max) / 2
    radius = np.linalg.norm(V - center, axis=1).max()
    print(f"  local bbox center: {[round(float(v),4) for v in center]}")
    print(f"  local bbox size: {[round(float(v),4) for v in (bb_max-bb_min)]}")
    print(f"  sphere radius: {radius*1000:.2f}mm")
    # 球心的世界坐标 (用matrix_world变换局部中心)
    wc = mw @ Vector(center)
    print(f"  world sphere center: {[round(float(v),4) for v in wc]}")

print("=== 3DDFA targets ===")
import json
d = json.load(open(DDFA_JSON, encoding="utf-8"))
print("L:", [round(v,4) for v in d["L"]["center_3d"]])
print("R:", [round(v,4) for v in d["R"]["center_3d"]])
