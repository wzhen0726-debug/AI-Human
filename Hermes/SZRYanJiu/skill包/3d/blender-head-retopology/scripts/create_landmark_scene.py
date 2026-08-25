"""
Reusable template: Create a landmark scene for user-driven empty marking.

Usage:
  blender --background --factory-startup --python create_landmark_scene.py -- <glb_path> <output_blend>

This script:
1. Imports a GLB model
2. Rotates to standard orientation (Z=height, X=width, Y=depth, front=-Y)
3. Scales to 1.8m height, centers, grounds at Z=0
4. Creates 16 bilingual (Chinese+English) named empty objects with descriptions
5. All empties have show_in_front=True and color=(1,0,0,1) (red)
6. Saves the blend file for user to open in Blender GUI and mark landmarks

The rotation uses the v5 confirmed 3-step matrix_basis method:
  Step 1: Rotate -90° around X (Y=height lying → Z=height standing)
  Step 2: Rotate -90° around Z (arms from Y → X)
  Step 3: Rotate -90° around Y (swap X/Z to fix misalignment)

If the model has a different original orientation, modify the rotation
steps based on extreme-point analysis (see references/blender-rotation-euler-failure.md).

After user marks landmarks and saves, read coordinates with:
  for e in bpy.data.objects:
      if e.type == 'EMPTY' and e.name.startswith('LM_'):
          print(f"{e.name}: {e.matrix_world.translation}")
"""
import bpy, os, sys, math
from mathutils import Vector, Matrix

# Parse args
if '--' in sys.argv:
    argv = sys.argv[sys.argv.index('--') + 1:]
    GLB_PATH = argv[0]
    OUT_BLEND = argv[1]
else:
    GLB_PATH = r"input/raw_model.glb"
    OUT_BLEND = r"output/landmark_scene.blend"

print("="*60)
print("Create Landmark Scene")
print("="*60)

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Import GLB
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

mesh_obj.name = "HighPoly"
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# === Rotation (v5 confirmed: 3-step matrix_basis) ===
# Original Tripo: Y=height(lying), Z=arm span, X=thickness
# Target: Z=height, X=width(arms), Y=depth(front=-Y)
for axis in ['X', 'Z', 'Y']:
    mesh_obj.matrix_basis = Matrix.Rotation(math.radians(-90), 4, axis) @ mesh_obj.matrix_basis
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# === Scale to 1.8m and ground ===
def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
        'size': Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))),
        'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    }

bbox = get_bbox(mesh_obj)
scale_factor = 1.8 / bbox['size'].z
mesh_obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
mesh_obj.location.x = -bbox['center'].x
mesh_obj.location.y = -bbox['center'].y
mesh_obj.location.z = -bbox['min'].z
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bbox = get_bbox(mesh_obj)
print(f"Model: H={bbox['size'].z:.2f}m W={bbox['size'].x:.2f}m D={bbox['size'].y:.2f}m")

# === Create 16 landmark empties ===
# Bilingual names, show_in_front=True, position descriptions
# Y: -Y=front(face/chest), +Y=back, 0=center(arms)
landmarks = [
    ("LM_01_头顶_head_top", "头顶正中(从正上方看,头部最高点的中心,标在头顶表面)", (0, -0.02, 1.75)),
    ("LM_02_下巴_chin", "下巴尖(下颌骨最前端,从正面看最下方的突出点)", (0, -0.08, 1.52)),
    ("LM_03_胸口_chest", "胸口正中(两乳头连线中点,正面)", (0, -0.08, 1.38)),
    ("LM_04_腹部_abdomen", "肚脐(腹部正中,正面)", (0, -0.06, 1.10)),
    ("LM_05_后背_back", "后背正中(与胸口对应的高度,背面)", (0, 0.08, 1.38)),
    ("LM_06_骨盆_pelvis", "骨盆正中(裆部上方,正面)", (0, -0.04, 0.92)),
    ("LM_07_左肩_shoulder_L", "左肩关节(手臂与躯干连接处,从上方看是凹陷点)", (-0.22, -0.02, 1.48)),
    ("LM_08_左肘_elbow_L", "左肘关节(手臂中段弯曲处,标在手臂中心)", (-0.55, -0.02, 1.48)),
    ("LM_09_左腕_wrist_L", "左手腕(手掌与手臂连接处,标在手臂中心)", (-0.85, -0.02, 1.48)),
    ("LM_10_右肩_shoulder_R", "右肩关节(手臂与躯干连接处,从上方看是凹陷点)", (0.22, -0.02, 1.48)),
    ("LM_11_右肘_elbow_R", "右肘关节(手臂中段弯曲处,标在手臂中心)", (0.55, -0.02, 1.48)),
    ("LM_12_右腕_wrist_R", "右手腕(手掌与手臂连接处,标在手臂中心)", (0.85, -0.02, 1.48)),
    ("LM_13_左膝_knee_L", "左膝盖(膝盖骨正前方)", (-0.12, -0.04, 0.50)),
    ("LM_14_左踝_ankle_L", "左脚踝(踝关节正前方)", (-0.12, -0.02, 0.06)),
    ("LM_15_右膝_knee_R", "右膝盖(膝盖骨正前方)", (0.12, -0.04, 0.50)),
    ("LM_16_右踝_ankle_R", "右脚踝(踝关节正前方)", (0.12, -0.02, 0.06)),
]

for name, desc, loc in landmarks:
    bpy.ops.object.empty_add(type='SPHERE', radius=0.015)
    empty = bpy.context.active_object
    empty.name = name
    empty.location = loc
    empty.color = (1.0, 0.0, 0.0, 1.0)
    empty["description"] = desc
    empty.show_in_front = True  # Display in front of mesh
    print(f"  {name}: {desc}")

# Save
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\nSaved: {OUT_BLEND}")
print("DONE")
