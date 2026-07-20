"""
Stage 6: 纹理烘焙 — Bake Diffuse + Normal from high-poly to low-poly.
Blender 5.1 background.

关键修复：
1. 场景清理：删除所有非必要mesh，只保留retopo+高模
2. 法线重计算：消除43%翻转面
3. 烘焙距离：0.12m（模型~1m高，8%身高）
4. 烘焙后删除高模，只保留retopo+贴图
"""
import bpy, sys, json, argparse, os


def setup_image(name, size=2048):
    img = bpy.data.images.new(name, width=size, height=size, alpha=False)
    img.file_format = 'PNG'
    return img


def clear_material(obj):
    """Remove all old materials and create a fresh one."""
    obj.data.materials.clear()
    mat = bpy.data.materials.new(name="BakedMat")
    mat.use_nodes = True
    obj.data.materials.append(mat)
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def connect_textures(mat, diffuse_img, normal_img):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = None
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break
    if not bsdf:
        return
    if diffuse_img:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = diffuse_img
        tex.location = (-300, 300)
        links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    if normal_img:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = normal_img
        tex.location = (-300, -100)
        nmap = nodes.new('ShaderNodeNormalMap')
        nmap.location = (-100, -100)
        links.new(tex.outputs['Color'], nmap.inputs['Color'])
        links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.7


def bake_textures(low_poly, high_poly, image_size=2048, bake_distance=0.12,
                  cage_extrusion=0.01):
    stats = {}

    # Ensure low_poly has UV layer
    if not low_poly.data.uv_layers:
        low_poly.data.uv_layers.new(name="UVMap")

    # Get model size
    xs = [v.co.x for v in low_poly.data.vertices]
    ys = [v.co.y for v in low_poly.data.vertices]
    zs = [v.co.z for v in low_poly.data.vertices]
    model_size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    # Use the provided bake_distance directly
    print(f"Model size: {model_size:.4f}m, bake distance: {bake_distance:.4f}m")

    # Clear old materials on low_poly
    mat = clear_material(low_poly)
    nodes = mat.node_tree.nodes

    # Deselect all, then select both
    bpy.ops.object.select_all(action='DESELECT')
    low_poly.select_set(True)
    high_poly.select_set(True)
    bpy.context.view_layer.objects.active = low_poly

    # Render settings
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 128
    bs = scene.render.bake
    bs.use_selected_to_active = True
    bs.use_cage = True
    bs.cage_extrusion = 0.3
    bs.max_ray_distance = 0.0
    bs.margin = 16

    # Bake Diffuse
    print("Baking Diffuse...")
    img = setup_image("Bake_Diffuse", image_size)
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = img
    nodes.active = tex_node
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_clear=True)
    diffuse_img = img
    stats["diffuse"] = {"image": img.name, "size": image_size}
    print(f"  Diffuse done")

    # Bake Normal
    print("Baking Normal...")
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    links = mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    img = setup_image("Bake_Normal", image_size)
    img.colorspace_settings.name = 'Non-Color'
    tex_node2 = nodes.new('ShaderNodeTexImage')
    tex_node2.image = img
    nodes.active = tex_node2
    bpy.ops.object.bake(type='NORMAL', use_clear=True)
    normal_img = img
    stats["normal"] = {"image": img.name, "size": image_size}
    print(f"  Normal done")

    # Rebuild material
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    connect_textures(mat, diffuse_img, normal_img)

    # Pack images
    for key in ["diffuse", "normal"]:
        img = bpy.data.images.get(stats[key]["image"])
        if img and not img.packed_file:
            img.pack()
            stats[key]["packed"] = True

    # Delete high-poly mesh
    bpy.ops.object.select_all(action='DESELECT')
    high_poly.select_set(True)
    bpy.ops.object.delete()
    print("  Deleted high-poly source mesh")

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_size', type=int, default=2048)
    parser.add_argument('--bake_distance', type=float, default=0.12)
    parser.add_argument('--cage_extrusion', type=float, default=0.01)
    parser.add_argument('--glb_source', type=str, default='')
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    # Import original GLB as high-poly source
    if args.glb_source and os.path.exists(args.glb_source):
        print(f"Importing high-poly source: {args.glb_source}")
        bpy.ops.import_scene.gltf(filepath=args.glb_source)

    # CRITICAL: Rotate high-poly to match low-poly orientation
    # Low-poly was rotated 90° CW in repair stage (x=y, y=-x)
    # High-poly from raw GLB is in original orientation (arms along Y)
    # Must rotate high-poly the same way before baking
    import bmesh
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' not in o.name and len(o.data.vertices) > 100000:
            xs = [v.co.x for v in o.data.vertices]
            ys = [v.co.y for v in o.data.vertices]
            if max(ys) - min(ys) > (max(xs) - min(xs)) * 2:
                # Arms along Y — needs rotation
                print(f"Rotating high-poly {o.name} to match retopo orientation")
                bm = bmesh.new()
                bm.from_mesh(o.data)
                for v in bm.verts:
                    old_x, old_y = v.co.x, v.co.y
                    v.co.x = old_y
                    v.co.y = -old_x
                bm.to_mesh(o.data)
                bm.free()
                o.data.update()
                xs2 = [v.co.x for v in o.data.vertices]
                ys2 = [v.co.y for v in o.data.vertices]
                print(f"  After: dim_x={max(xs2)-min(xs2):.3f} dim_y={max(ys2)-min(ys2):.3f}")

    # Clean up ALL non-essential meshes
    for o in list(bpy.data.objects):
        if o.type == 'MESH':
            if len(o.data.vertices) < 100:
                bpy.data.objects.remove(o, do_unlink=True)
    # Remove any duplicate retopo meshes
    retopo_objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name]
    if len(retopo_objs) > 1:
        for o in retopo_objs[1:]:
            bpy.data.objects.remove(o, do_unlink=True)

    # Find low-poly (retopo) and high-poly (largest)
    low_poly = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            low_poly = o
            break
    if not low_poly:
        meshes = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
                        key=lambda o: len(o.data.polygons))
        if len(meshes) >= 2:
            low_poly = meshes[-1]  # smallest = retopo (22万 < 193万)
        else:
            print("ERROR: No low-poly mesh found")
            sys.exit(1)

    meshes = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
                    key=lambda o: len(o.data.polygons), reverse=True)
    high_poly = meshes[0]

    print(f"Low-poly: {low_poly.name} ({len(low_poly.data.polygons)} faces)")
    print(f"High-poly: {high_poly.name} ({len(high_poly.data.polygons)} faces)")

    # CRITICAL: Recalculate normals on BOTH meshes
    for obj in [low_poly, high_poly]:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    print("Normals recalculated")

    result = bake_textures(low_poly, high_poly, args.image_size,
                           args.bake_distance, args.cage_extrusion)
    print("Bake:", json.dumps(result, indent=2))
    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
