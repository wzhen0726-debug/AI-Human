"""Render multi-view screenshots of a mesh for vision_analyze self-check.

3 views (front / side / three-quarter), workbench engine, studio light,
camera positioned via spherical coordinates around model bbox center.

Usage:
  blender --background model.blend --factory-startup --python render_screenshot.py

Outputs repair_screenshot_{front,side,three_quarter}.png next to the .blend.

Common pitfalls (all hit on 2026-07-23):
1. `to_track_quat` is a Vector method — convert tuple to mathutils.Vector first.
2. Blender camera forward is -Z, NOT +Z. Use look_dir.to_track_quat('-Z', 'Y')
   — using 'Z' makes the camera face AWAY from the model (all-black render).
3. Camera distance = max(dims) * 1.5, not 2.5 — at 2.5x the model fills
   only ~5% of the frame on a 1m character at 1024x1024.
4. Engine 'BLENDER_WORKBENCH' with studio light + cavity shading renders
   fast (2-3s for 1.9M faces) and shows geometry clearly for vision_analyze.
"""
import bpy, sys, os, math
from mathutils import Vector


def get_main_mesh():
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.data.vertices) > 100:
            return obj
    return None


def render_views(obj, out_dir, prefix="screenshot", dist_factor=1.5,
                 resolution=1024):
    """Render 3 standard views of obj. Returns list of saved paths."""
    mesh = obj.data
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    mn = (min(xs), min(ys), min(zs))
    mx = (max(xs), max(ys), max(zs))
    dims = (mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2])
    center = ((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2)

    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'WORLD'
    scene.display.shading.curvature_ridge_factor = 1.5
    scene.display.shading.curvature_valley_factor = 1.0

    cam = bpy.data.objects.get("Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam

    views = [
        ("front", 0, 0),
        ("side", math.pi/2, 0),
        ("three_quarter", math.pi/4, math.pi/6),
    ]

    saved = []
    for name, rot_y, rot_z in views:
        dist = max(dims) * dist_factor
        cam_x = center[0] + dist * math.sin(rot_y) * math.cos(rot_z)
        cam_y = center[1] - dist * math.cos(rot_y) * math.cos(rot_z)
        cam_z = center[2] + dist * math.sin(rot_z)
        cam.location = (cam_x, cam_y, cam_z)

        # Camera forward is -Z; use '-Z' axis to track look direction
        look_dir = Vector((center[0]-cam_x, center[1]-cam_y, center[2]-cam_z))
        cam.rotation_euler = look_dir.to_track_quat('-Z', 'Y').to_euler()

        path = os.path.join(out_dir, f"{prefix}_{name}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        saved.append(path)
        print(f"Saved: {path}")

    return saved


def main():
    obj = get_main_mesh()
    if not obj:
        print("ERROR: No mesh found")
        sys.exit(1)
    out_dir = os.path.dirname(bpy.data.filepath)
    render_views(obj, out_dir, prefix="repair_screenshot")
    print("All screenshots saved.")


if __name__ == "__main__":
    main()
