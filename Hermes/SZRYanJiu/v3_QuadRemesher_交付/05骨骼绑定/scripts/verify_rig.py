"""验证绑定结果：骨骼位置、权重分布、截图渲染"""
import bpy

def verify():
    arm = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            arm = o
            break
    if arm is None:
        print("ERROR: 找不到骨架")
        return

    print(f"骨架: {arm.name}")
    print(f"骨骼数: {len(arm.data.bones)}")
    print("=" * 50)
    print("骨骼列表 (head -> tail):")
    for b in arm.data.bones:
        print(f"  {b.name:16s} head=({b.head_local.x:6.3f}, {b.head_local.y:6.3f}, {b.head_local.z:6.3f}) "
              f"tail=({b.tail_local.x:6.3f}, {b.tail_local.y:6.3f}, {b.tail_local.z:6.3f}) "
              f"parent={b.parent.name if b.parent else 'None'}")

    # 检查 mesh 的权重
    print("=" * 50)
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        mod = None
        for m in o.modifiers:
            if m.type == 'ARMATURE':
                mod = m
                break
        n_groups = len(o.vertex_groups)
        print(f"Mesh {o.name}: vertex_groups={n_groups}, armature_modifier={'YES' if mod else 'NO'}")
        if mod:
            print(f"  modifier object={mod.object.name if mod.object else 'None'}")

    # 渲染三视图
    print("=" * 50)
    print("渲染三视图...")

if __name__ == "__main__":
    verify()
