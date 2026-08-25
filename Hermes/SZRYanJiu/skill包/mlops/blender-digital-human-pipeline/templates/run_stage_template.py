"""
One-click stage launcher template.
Copy this for each pipeline stage (run_repair.py, run_adhesion.py, run_remesh.py, etc).

Usage by leadership/technician:
  cd test03_SimplifiedPipeline
  blender --background --factory-startup --python scripts\run_<stage>.py

The launcher handles all path logic — no --python-expr quoting issues.
"""
import bpy, sys, os

# === Path configuration (copy & adjust per stage) ===
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
INPUT_BLEND = os.path.join(PROJECT_DIR, "v6_run", "01_repair.blend")  # prev stage output
OUTPUT_BLEND = os.path.join(PROJECT_DIR, "v6_run", "02_adhesion.blend")  # this stage output

print("=" * 60)
print("Stage: <stage_name>")
print(f"Input:  {INPUT_BLEND}")
print(f"Output: {OUTPUT_BLEND}")
print("=" * 60)

# Import stage module
sys.path.insert(0, SCRIPTS_DIR)
import <stage_module>  # e.g. import adhesion

# 1. Open input blend (or import GLB for first stage)
bpy.ops.wm.open_mainfile(filepath=INPUT_BLEND)
# For first stage: bpy.ops.import_scene.gltf(filepath=GLB_PATH)

# 2. Get mesh
obj = <stage_module>.get_main_mesh()
if not obj:
    print("ERROR: No mesh found")
    sys.exit(1)

# 3. Run stage pipeline
result = <stage_module>.<pipeline_function>(obj)

# 4. Save
os.makedirs(os.path.dirname(OUTPUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
print(f"\n保存完成: {OUTPUT_BLEND}")
print("=" * 60)
