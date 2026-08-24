"""GLB 导入验证"""
import bpy
import sys

def main():
    glb_path = None
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
        if argv:
            glb_path = argv[0]

    if not glb_path:
        print("用法: -- <glb_path>")
        return

    bpy.ops.import_scene.gltf(filepath=glb_path)
    print("=== GLB 导入验证 ===")
    for o in bpy.data.objects:
        print(f"  {o.name}: type={o.type}")

    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if arm:
        print(f"骨架骨骼数: {len(arm[0].data.bones)}")
        print(f"骨骼: {[b.name for b in arm[0].data.bones]}")

    # 检查 mesh 的权重
    for o in bpy.data.objects:
        if o.type == 'MESH':
            mod = [m for m in o.modifiers if m.type == 'ARMATURE']
            print(f"  {o.name}: vertex_groups={len(o.vertex_groups)}, armature_mod={'YES' if mod else 'NO'}")

if __name__ == "__main__":
    main()
