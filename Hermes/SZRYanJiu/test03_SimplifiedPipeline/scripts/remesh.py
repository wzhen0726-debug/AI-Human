"""
Stage 4: Quad Remesher — 20-25万面, Adaptive Size.
Blender 5.1 background script. Uses bpy.context.scene.qremesher properties.
Quad Remesher addon must be enabled (not --factory-startup).
"""
import bpy, sys, json, argparse, os, time


def get_main_mesh():
    """Get the largest mesh, skip default cube."""
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) < 100:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        return None
    meshes.sort(key=lambda x: x[1], reverse=True)
    return meshes[0][0]


def quad_remesh(obj, target_count=200000, use_symmetry_x=False,
                detect_hard_edges=True, adaptive_size=50.0):
    """Run Quad Remesher using scene properties API."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    stats = {
        "initial_verts": len(obj.data.vertices),
        "initial_faces": len(obj.data.polygons),
    }

    # Set Quad Remesher parameters via scene properties
    qr = bpy.context.scene.qremesher
    qr.target_count = target_count
    qr.symmetry_x = use_symmetry_x
    qr.symmetry_y = False
    qr.symmetry_z = False
    qr.autodetect_hard_edges = detect_hard_edges
    qr.adaptive_size = adaptive_size
    qr.adapt_quad_count = True

    print(f"QR Settings: target={qr.target_count}, sym_x={qr.symmetry_x}, "
          f"hard_edges={qr.autodetect_hard_edges}, adaptive={qr.adaptive_size}")

    # Clean up any previous QR temp files
    temp_dir = r'C:/Users/Liyunzhong/AppData/Local/Temp/Exoside/QuadRemesher/Blender'
    progress_file = os.path.join(temp_dir, 'progress.txt')
    retopo_path = os.path.join(temp_dir, 'retopo.fbx')
    settings_path = os.path.join(temp_dir, 'RetopoSettings.txt')
    for f in [progress_file, retopo_path, settings_path]:
        if os.path.exists(f):
            os.remove(f)
            print(f"  Cleaned: {f}")

    # Run Quad Remesher — QR runs as external exe, but the operator needs the addon.
    # If addon not installed, manually trigger QR via the temp folder workflow.
    qr_addon_loaded = False
    try:
        bpy.ops.qremesher.remesh()
        print("qremesher.remesh() called - waiting for external process...")
        qr_addon_loaded = True
    except Exception as e:
        print(f"qremesher operator not available: {e}")
        print("Trying manual QR trigger...")
        # Write settings file manually
        os.makedirs(temp_dir, exist_ok=True)
        settings_content = f"""HostApp=Blender
FileIn="{os.path.join(temp_dir, 'inputMesh.fbx')}"
FileOut="{retopo_path}"
ProgressFile="{progress_file}"
TargetQuadCount={target_count}
CurvatureAdaptivness={adaptive_size}
ExactQuadCount=0
UseVertexColorMap=False
UseMaterialIds=0
UseIndexedNormals=0
AutoDetectHardEdges={1 if detect_hard_edges else 0}
"""
        with open(settings_path, 'w') as f:
            f.write(settings_content)
        # Export input mesh as FBX
        input_fbx = os.path.join(temp_dir, 'inputMesh.fbx')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.ops.export_scene.fbx(filepath=input_fbx, use_selection=True,
                                  mesh_smooth_type='FACE', bake_anim=False)
        # Find and run QR exe
        qr_exe = None
        search_paths = [
            r'C:/Program Files/Exoside/QuadRemesher/QuadRemesher.exe',
            r'C:/Program Files (x86)/Exoside/QuadRemesher/QuadRemesher.exe',
        ]
        for p in search_paths:
            if os.path.exists(p):
                qr_exe = p
                break
        if qr_exe:
            import subprocess
            print(f"Running QR: {qr_exe}")
            subprocess.run([qr_exe, '-settings', settings_path], timeout=300)
        else:
            print("QR exe not found, checking if retopo.fbx already exists from previous run...")
            if os.path.exists(retopo_path) and os.path.getsize(retopo_path) > 100000:
                print("Using existing retopo.fbx")
            else:
                stats["error"] = "QR exe not found and no existing retopo.fbx"
                return stats

    # Poll until QR external process completes
    print("Waiting for QuadRemesher external process...")
    for i in range(600):  # 10 minute timeout
        time.sleep(1)
        if os.path.exists(retopo_path) and os.path.getsize(retopo_path) > 100000:
            stats["qr_progress"] = "complete"
            break
        if os.path.exists(progress_file):
            with open(progress_file) as f:
                content = f.read().strip()
            try:
                pct = float(content)
                if i > 30 and pct == 0.0:
                    stats["qr_progress"] = "stalled"
                    break
            except ValueError:
                pass
        if i % 30 == 0:
            print(f"  Still waiting [{i}s]...")

    # Import retopo result
    if os.path.exists(retopo_path) and os.path.getsize(retopo_path) > 100000:
        print(f"Importing retopo result ({os.path.getsize(retopo_path)} bytes)...")
        bpy.ops.import_scene.fbx(filepath=retopo_path)
        stats["retopo_imported"] = True
        retopo_obj = None
        for o in bpy.data.objects:
            if o.type == 'MESH' and 'Retopo' in o.name:
                retopo_obj = o
                stats["retopo_verts"] = len(o.data.vertices)
                stats["retopo_faces"] = len(o.data.polygons)
                stats["retopo_name"] = o.name
                break
        if retopo_obj:
            # Position retopo at same location as original
            retopo_obj.location = obj.location
            retopo_obj.rotation_euler = obj.rotation_euler
            retopo_obj.scale = obj.scale
    else:
        stats["retopo_imported"] = False
        stats["qr_progress"] = stats.get("qr_progress", "timeout")

    if os.path.exists(settings_path):
        with open(settings_path) as f:
            stats["qr_settings"] = f.read().strip()[:500]

    stats["final_verts"] = len(obj.data.vertices)
    stats["final_faces"] = len(obj.data.polygons)
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_count', type=int, default=250000)
    parser.add_argument('--symmetry_x', type=lambda s: s.lower() == 'true', default=False)
    parser.add_argument('--hard_edges', type=lambda s: s.lower() == 'true', default=True)
    parser.add_argument('--adaptive_size', type=float, default=50.0)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh found")
        sys.exit(1)

    result = quad_remesh(obj, args.target_count, args.symmetry_x,
                         args.hard_edges, args.adaptive_size)
    print("Quad Remesher Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
