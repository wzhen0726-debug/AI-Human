"""修复两个小问题 (2026-08-26):
1. 文字牌挡住右手 → 挪到身体左侧 (x=-1.1, 与右手区错开)
2. 默认视角微侧透视 → 所有工作区的3D视口强制纯正面-Y视角+正交
"""
import bpy
from mathutils import Vector, Quaternion

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\A_半自动打点\06_rig_markers.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)

# --- 修复1: 文字牌挪到左侧 (原0.9,-1.2,1.5 挡右手区) ---
for o in bpy.data.objects:
    if o.type == 'FONT' and o.name.startswith("打点操作提示"):
        o.location = Vector((-1.1, -1.2, 1.5))   # 左前方
        print(f"文字牌已挪到: {o.location[:]}  (x<0 左侧, 不挡右手)")

# --- 修复2: 所有视口强制纯正面 ---
# 纯正面: 相机在+Y看向-Y, 四元数(1,0,0,0)绕X轴转90° → rot=(0.707,0.707,0,0)
# 但用户说之前存的是微微侧着的 → 强制覆盖所有视口为精确值
VIEW_ROT = Quaternion((1.0, 0.0, 0.0), 1.5708)   # 绕X轴+90° = 纯正面
VIEW_LOC = Vector((0.0, 0.0, 0.9))
VIEW_DIST = 3.0

count = 0
for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    r3d = sp.region_3d
                    r3d.view_location = VIEW_LOC
                    r3d.view_rotation = VIEW_ROT
                    r3d.view_distance = VIEW_DIST
                    r3d.view_perspective = 'ORTHO'
                    sp.shading.type = 'MATERIAL'
                    count += 1

print(f"共强制 {count} 个3D视口为纯正面-Y视角")

# --- 保存 ---
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"已保存: {BLEND}")
print("FIX_SIGN_VIEWPORT_DONE")
