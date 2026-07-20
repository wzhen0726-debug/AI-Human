"""
Single-stage launcher for the simplified pipeline.
Usage:
  blender --background [blend_file] --python launcher.py -- <stage>

Stages: repair, adhesion, remesh, uv, bake, rig, glb

Note: repair/remesh stages do NOT use --factory-startup (need QR + ARP addons).
      Other stages use --factory-startup for clean state.
"""
import bpy, sys, os

# Parse stage from argv after --
STAGE = None
if '--' in sys.argv:
    args = sys.argv[sys.argv.index('--') + 1:]
    if args:
        STAGE = args[0]

SCRIPTS = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test03_SimplifiedPipeline\scripts"
GLB = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test03_SimplifiedPipeline\input\raw_model.glb"
RD = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
sys.path.insert(0, SCRIPTS)

print(f"LAUNCHER: stage={STAGE}, cwd={RD}")

if STAGE == "repair":
    # Import GLB first
    bpy.ops.import_scene.gltf(filepath=GLB)
    import repair
    obj = repair.get_main_mesh()
    if not obj:
        print("ERROR: No mesh after GLB import")
        sys.exit(1)
    result = repair.repair_pipeline(obj, 0.005, 3, 0.3)
    print(f"REPAIR: {result}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "01_repair.blend"))

elif STAGE == "adhesion":
    import adhesion
    obj = adhesion.get_main_mesh()
    if not obj:
        print("ERROR: No mesh")
        sys.exit(1)
    if len(obj.data.polygons) > 100000:
        print(f"ADH:SKIP ({len(obj.data.polygons)} faces, already watertight)")
    else:
        pairs = adhesion.detect_adhesion(obj)
        print(f"ADH:{len(pairs)} pairs")
        if pairs:
            adhesion.fix_adhesion(obj, pairs)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "02_adhesion.blend"))

elif STAGE == "remesh":
    # Enable Quad Remesher addon (don't use factory-startup for this)
    try:
        bpy.ops.preferences.addon_enable(module='quad_remesh')
        print("Quad Remesher addon enabled")
    except Exception as e:
        print(f"QR enable: {e}")
    import remesh
    obj = remesh.get_main_mesh()
    if not obj:
        print("ERROR: No mesh")
        sys.exit(1)
    result = remesh.quad_remesh(obj, 100000, False, True, 50.0)
    print(f"REMESH: {result}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "03_remesh.blend"))

elif STAGE == "uv":
    import uv
    meshes = [(o, len(o.data.vertices)) for o in bpy.data.objects if o.type == 'MESH']
    meshes.sort(key=lambda x: x[1], reverse=True)
    obj = meshes[0][0]
    # Use the retopo mesh (lower vert count, the one we want UV on)
    retopo = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            retopo = o
            break
    if not retopo:
        retopo = meshes[0][0]
    result = uv.auto_uv_pipeline(retopo)
    print(f"UV: {result}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "04_uv.blend"))

elif STAGE == "bake":
    import bake, bmesh
    # Import original GLB as high-poly source
    bpy.ops.import_scene.gltf(filepath=GLB)
    # CRITICAL: Rotate high-poly to match retopo orientation
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' not in o.name and len(o.data.vertices) > 100000:
            xs = [v.co.x for v in o.data.vertices]
            ys = [v.co.y for v in o.data.vertices]
            if max(ys) - min(ys) > (max(xs) - min(xs)) * 2:
                print(f"Rotating high-poly {o.name}")
                bm = bmesh.new(); bm.from_mesh(o.data)
                for v in bm.verts:
                    old_x, old_y = v.co.x, v.co.y
                    v.co.x = old_y; v.co.y = -old_x
                bm.to_mesh(o.data); bm.free(); o.data.update()
    # Clean up ALL tiny objects
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and len(o.data.vertices) < 100:
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove duplicate retopo meshes — keep only one
    retopo_objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'Retopo' in o.name]
    if len(retopo_objs) > 1:
        for o in retopo_objs[1:]:
            bpy.data.objects.remove(o, do_unlink=True)
    # Find retopo (low) and largest mesh (high)
    retopo = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            retopo = o; break
    if not retopo:
        all_m = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
                       key=lambda o: len(o.data.polygons))
        retopo = all_m[-1]
    all_m = sorted([o for o in bpy.data.objects if o.type == 'MESH'],
                   key=lambda o: len(o.data.polygons), reverse=True)
    high = all_m[0]
    # Recalc normals on both
    for obj in [retopo, high]:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    print(f"BAKE: low={retopo.name}({len(retopo.data.polygons)}) high={high.name}({len(high.data.polygons)})")
    result = bake.bake_textures(retopo, high, 2048, 0.12, 0.01)
    print(f"BAKE: {result}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "05_bake.blend"))

elif STAGE == "rig":
    # Enable Auto-Rig Pro
    try:
        bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
        print("ARP addon enabled")
    except Exception as e:
        print(f"ARP enable: {e}")
    prefs = bpy.context.preferences.addons.get('auto_rig_pro-master')
    if prefs and hasattr(prefs, 'preferences'):
        prefs.preferences.ai_presets_path = r'C:/Users/Liyunzhong/Documents/AutoRigPro/AI'
        print("ARP AI path set")
    import rig
    mesh = rig.get_retopo_mesh()
    if not mesh:
        print("ERROR: No mesh")
        sys.exit(1)
    result = rig.arp_smart_rig(mesh)
    print(f"RIG: {result}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RD, "06_rig.blend"))

elif STAGE == "glb":
    import export_glb
    result = export_glb.export_glb(os.path.join(RD, "final.glb"))
    print(f"GLB: {result}")

else:
    print(f"Unknown stage: {STAGE}")
    print("Available: repair, adhesion, remesh, uv, bake, rig, glb")

print(f"STAGE {STAGE}: DONE")
