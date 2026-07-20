# Tripo AI high-poly to Blender compliant digital human full automation pipeline v1.0
import bpy, os, math, numpy as np
from mathutils import Vector, Matrix

OUTPUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\output_final"
TRIPO = r"E:\WangZhen_Project\AI\ShuZiRen\Zed\ShiJueShiBieMesh\原始GLB\原始Tripo高模\tripo_01.glb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_world_verts(obj):
    return np.array([obj.matrix_world @ v.co for v in obj.data.vertices])

print("=" * 70)
print("Stage 1: Import + Bounding Box Analysis")
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=TRIPO)
tripo = None
for obj in bpy.data.objects:
    if obj.type == "MESH":
        tripo = obj
        break

verts = get_world_verts(tripo)
print(f"  Original: {len(tripo.data.vertices):,} verts, {len(tripo.data.polygons):,} faces")
print(f"  BBox: X[{verts[:,0].min():.3f},{verts[:,0].max():.3f}] Y[{verts[:,1].min():.3f},{verts[:,1].max():.3f}] Z[{verts[:,2].min():.3f},{verts[:,2].max():.3f}]")

print("\nStage 2: Auto Orientation")
ranges = {
    "X": verts[:,0].max() - verts[:,0].min(),
    "Y": verts[:,1].max() - verts[:,1].min(),
    "Z": verts[:,2].max() - verts[:,2].min()
}
height_axis = max(ranges, key=ranges.get)
print(f"  Height axis: {height_axis} ({ranges[height_axis]:.3f}m)")

# Use direct vertex rotation because transform_apply doesn't work reliably in background mode
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

if height_axis == "X":
    rot_mat = Matrix.Rotation(math.radians(-90), 3, 'Z')
elif height_axis == "Y":
    rot_mat = Matrix.Rotation(math.radians(-90), 3, 'X')
else:
    rot_mat = Matrix.Identity(3)

for v in tripo.data.vertices:
    v.co = rot_mat @ v.co
tripo.data.update()

verts = get_world_verts(tripo)
print(f"  After orient: X[{verts[:,0].min():.3f},{verts[:,0].max():.3f}] Y[{verts[:,1].min():.3f},{verts[:,1].max():.3f}] Z[{verts[:,2].min():.3f},{verts[:,2].max():.3f}]")

center_z = (verts[:,2].min() + verts[:,2].max()) / 2
front_pts = verts[verts[:,2] > center_z]
back_pts = verts[verts[:,2] < center_z]
if len(back_pts) > len(front_pts) * 1.3:
    rot_y = Matrix.Rotation(math.radians(180), 3, 'Y')
    for v in tripo.data.vertices:
        v.co = rot_y @ v.co
    tripo.data.update()
    print("  Rotated 180 degrees to face -Y")
    verts = get_world_verts(tripo)

print("\nStage 3: Geometry Cleanup")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.delete_loose()
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")
print(f"  After cleanup: {len(tripo.data.vertices):,} verts, {len(tripo.data.polygons):,} faces")

print("\nStage 4: Decimate (target < 500K tris)")
current_faces = len(tripo.data.polygons)
if current_faces > 500000:
    ratio = 500000 / current_faces
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.decimate(ratio=ratio)
    bpy.ops.object.mode_set(mode="OBJECT")
print(f"  After decimate: {len(tripo.data.vertices):,} verts, {len(tripo.data.polygons):,} faces")

print("\nStage 5: Tris to Quads (partial)")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.tris_convert_to_quads()
bpy.ops.object.mode_set(mode="OBJECT")
quads = sum(1 for p in tripo.data.polygons if len(p.vertices) == 4)
tris = sum(1 for p in tripo.data.polygons if len(p.vertices) == 3)
print(f"  After convert: {len(tripo.data.vertices):,} verts, {len(tripo.data.polygons):,} faces (quads={quads}, tris={tris})")

print("\nStage 6: Rigify Binding")
bpy.ops.object.select_all(action="DESELECT")
bpy.ops.object.armature_human_metarig_add()
metarig = bpy.context.active_object
metarig.name = "MetaRig"

verts = get_world_verts(tripo)
min_x, max_x = verts[:,0].min(), verts[:,0].max()
min_y, max_y = verts[:,1].min(), verts[:,1].max()
min_z, max_z = verts[:,2].min(), verts[:,2].max()
center_x = (min_x + max_x) / 2
center_z = (min_z + max_z) / 2
height = max_y - min_y
width = max_x - min_x
depth = max_z - min_z
print(f"  Model: H={height:.3f}m W={width:.3f}m D={depth:.3f}m")

meta_scale = height / 2.0
metarig.scale = (meta_scale, meta_scale, meta_scale)
metarig.location = (center_x, 0, center_z)
bpy.context.view_layer.update()

tripo.select_set(True)
metarig.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
print("  Auto weight binding done")

bpy.context.view_layer.objects.active = metarig
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.select_all(action="SELECT")
bpy.ops.pose.rigify_generate()
bpy.ops.object.mode_set(mode="OBJECT")
print("  Rigify control rig generated")

rig_ctrl = None
for obj in bpy.data.objects:
    if obj.type == "ARMATURE" and "RIG-" in obj.name:
        rig_ctrl = obj
        break

print("\nStage 7: Cleanup Output")
if metarig:
    bpy.data.objects.remove(metarig, do_unlink=True)
    print("  Deleted original MetaRig")

wgt_col = bpy.data.collections.new(name="RigWidgets")
main_col = bpy.data.collections.new(name="Character")
bpy.context.scene.collection.children.link(wgt_col)
bpy.context.scene.collection.children.link(main_col)

for obj in list(bpy.data.objects):
    if obj.name.startswith("WGT-"):
        for col in obj.users_collection:
            col.objects.unlink(obj)
        wgt_col.objects.link(obj)

for obj in [tripo, rig_ctrl]:
    if obj:
        for col in obj.users_collection:
            col.objects.unlink(obj)
        main_col.objects.link(obj)

bpy.ops.object.select_all(action="DESELECT")
bpy.ops.object.select_by_type(type="CAMERA")
bpy.ops.object.select_by_type(type="LIGHT")
bpy.ops.object.delete()

print("\nStage 8: Save")
out_blend = os.path.join(OUTPUT_DIR, "tripo_final.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

tripo.select_set(True)
bpy.context.view_layer.objects.active = tripo
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUTPUT_DIR, "tripo_final.glb"),
    use_selection=True,
    export_format="GLB",
    export_apply=True
)

print(f"\n{'='*70}")
print("DONE!")
print(f"  blend: {out_blend}")
print(f"  verts: {len(tripo.data.vertices):,}")
print(f"  faces: {len(tripo.data.polygons):,} (quads={quads}, tris={tris})")
print(f"  rig: {rig_ctrl.name if rig_ctrl else 'N/A'}")
print(f"  collections: Character / RigWidgets")