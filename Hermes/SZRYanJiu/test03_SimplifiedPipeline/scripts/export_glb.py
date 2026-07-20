"""
Stage 8: 导出GLB — 只导出网格 + 有权重的骨骼（无控制器）。
Blender 5.1 background script.

用户要求：
1. 一个网格 + 有权重的绑好的骨骼
2. 不要控制器（引擎不支持）
3. 网格和骨骼有关联（parent + armature modifier）
"""
import bpy, sys, json, argparse, os


def get_retopo_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if meshes:
        meshes.sort(key=lambda x: x[1], reverse=True)
        return meshes[0][0]
    return None


def cleanup_scene():
    """Remove all non-essential objects: controllers, helper meshes, cameras, lights."""
    # Remove all control shape meshes (cs_user_*, c_*)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and ('cs_user' in o.name or 'c_' in o.name):
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove body_temp
    for o in list(bpy.data.objects):
        if 'body_temp' in o.name.lower():
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove high-poly source meshes
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and len(o.data.polygons) > 500000:
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove non-essential meshes (keep only retopo)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and 'Retopo' not in o.name:
            if len(o.data.vertices) < 100000:
                bpy.data.objects.remove(o, do_unlink=True)
    # Remove cameras, lights, empties (except armature children)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(o, do_unlink=True)


def clean_armature(arm, mesh):
    """Remove control bones, keep only deformation bones that have vertex weights."""
    # Get all vertex group names on the mesh
    vg_names = set(vg.name for vg in mesh.vertex_groups)
    
    # Mark deformation bones (bones that have matching vertex groups)
    deform_bones = set()
    for bone in arm.data.bones:
        if bone.name in vg_names:
            deform_bones.add(bone.name)
    
    # Also keep parents of deform bones (needed for hierarchy)
    to_keep = set()
    for name in deform_bones:
        bone = arm.data.bones.get(name)
        while bone:
            to_keep.add(bone.name)
            bone = bone.parent
    
    print(f"  Deform bones: {len(deform_bones)}")
    print(f"  Keeping (with parents): {len(to_keep)}")
    print(f"  Removing: {len(arm.data.bones) - len(to_keep)}")
    
    # Remove non-deform bones
    to_remove = [b for b in arm.data.bones if b.name not in to_keep]
    for bone in to_remove:
        arm.data.bones.remove(bone)
    
    return len(arm.data.bones)


def export_glb(output_path):
    """Export mesh + deformation armature only (no controllers)."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    cleanup_scene()

    mesh = get_retopo_mesh()
    if not mesh:
        return {"error": "No mesh found"}
    
    arm = None
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            arm = o
            break
    
    if not arm:
        return {"error": "No armature found"}

    # Ensure mesh has armature modifier pointing to armature
    has_arm_mod = False
    for mod in mesh.modifiers:
        if mod.type == 'ARMATURE':
            mod.object = arm
            mod.use_deform = True
            has_arm_mod = True
    if not has_arm_mod:
        mod = mesh.modifiers.new('Armature', 'ARMATURE')
        mod.object = arm
        mod.use_deform = True

    # Ensure mesh is parented to armature
    mesh.parent = arm
    mesh.parent_type = 'OBJECT'

    # Clean armature: remove non-deformation bones
    bone_count = clean_armature(arm, mesh)
    
    stats = {
        "mesh": mesh.name,
        "mesh_verts": len(mesh.data.vertices),
        "mesh_faces": len(mesh.data.polygons),
        "armature": arm.name,
        "bone_count": bone_count,
        "vertex_groups": len(mesh.vertex_groups),
    }

    # Select only mesh + armature for export
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm

    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            export_apply=True,
            export_animations=False,
            export_image_format='JPEG',
            export_texcoords=True,
            export_normals=True,
            export_materials='EXPORT',
            use_selection=True,
            export_yup=True,
            export_skins=True,
            export_extras=False,
            export_cameras=False,
            export_lights=False,
        )
        file_size = os.path.getsize(output_path)
        stats["file_size_mb"] = round(file_size / (1024 * 1024), 2)
        stats["output"] = output_path
        print(f"  GLB exported: {file_size} bytes")
    except Exception as e:
        stats["error"] = str(e)
        print(f"  GLB export failed: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, required=True)
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    result = export_glb(args.output)
    print("Export GLB Result:", json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
