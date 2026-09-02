import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\01_AI打点.blend")
# 确保约束被求值
dg = bpy.context.evaluated_depsgraph_get()
bpy.context.view_layer.update()
print("=== 用 matrix_world.translation (含约束结果) ===")
for base in ['elbow','shoulder','hand','thigh','knee','foot']:
    main = bpy.data.objects.get(base + '_loc')
    sym = bpy.data.objects.get(base + '_loc_sym')
    if main and sym:
        pm = main.evaluated_get(dg).matrix_world.translation
        ps = sym.evaluated_get(dg).matrix_world.translation
        sym_ok = abs(pm.x + ps.x) < 0.001 and abs(pm.y - ps.y) < 0.001 and abs(pm.z - ps.z) < 0.001
        print(f"{base}: 主({pm.x:.4f},{pm.y:.4f},{pm.z:.4f}) 镜像({ps.x:.4f},{ps.y:.4f},{ps.z:.4f}) 严格对称={'是' if sym_ok else '否'}")
