"""生成眼窝rim引导曲线: 从高模rim轮廓JSON提取, 导出为FBX曲线供QuadRemesher引导.
原理: QR的AutoDetectHardEdges+引导曲线能让四边形沿特征线排列, rim更锐利."""
import bpy, os, json
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "models", "02_rim_guides.blend")
OUT_FBX = os.path.join(DELIVERY, "02QuadRemesher拓扑", "models", "02_rim_guides.fbx")
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
cont = json.load(open(XZ_JSON, encoding="utf-8"))

# 每侧rim: 把轮廓点连成一条闭合曲线(眼睑缘)
for side in ("L", "R"):
    rim = cont[side]["rim_3d"]
    cu = bpy.data.curves.new(f"RimGuide_{side}", 'CURVE')
    cu.dimensions = '3D'
    spl = cu.splines.new('POLY')
    spl.points.add(len(rim) - 1)
    for i, p in enumerate(rim):
        spl.points[i].co = (*p, 1.0)
    spl.use_cyclic_u = True          # 闭合环
    ob = bpy.data.objects.new(f"RimGuide_{side}", cu)
    bpy.context.scene.collection.objects.link(ob)
    print(f"{side}: rim引导曲线 {len(rim)}点 闭合")

bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
# 导出FBX(QR读取用)
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=False)
print(f"FBX: {OUT_FBX} ({os.path.getsize(OUT_FBX)/1024:.0f}KB)")
print("RIM_GUIDE_DONE")
