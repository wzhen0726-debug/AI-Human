import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831\01_AI打点.blend")
print("=== _sym点 镜像约束详情 ===")
for base in ['elbow','shoulder','hand','thigh','knee','foot']:
    sym = bpy.data.objects.get(base + '_loc_sym')
    if not sym: continue
    print(f"\n{base}_loc_sym: 实际location=({sym.location.x:.4f},{sym.location.y:.4f},{sym.location.z:.4f})")
    for c in sym.constraints:
        info = f"  [{c.type}] target={c.target.name if c.target else None}"
        if c.type == 'COPY_LOCATION':
            info += f" use_x={c.use_x} use_y={c.use_y} use_z={c.use_z} invert=({c.invert_x},{c.invert_y},{c.invert_z}) owner_space={c.owner_space} target_space={c.target_space} influence={c.influence}"
        if c.type == 'LIMIT_LOCATION':
            info += f" use_min_x={c.use_min_x} min_x={c.min_x:.3f} owner_space={c.owner_space}"
        print(info)
# 检查主点有没有被改过(主点应该也有对称标记?)
print("\n=== 主点 ===")
for base in ['elbow','shoulder']:
    main = bpy.data.objects.get(base + '_loc')
    if main:
        print(f"{base}_loc: location=({main.location.x:.4f},{main.location.y:.4f},{main.location.z:.4f}) 约束={[c.type for c in main.constraints]}")
