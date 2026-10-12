"""Render front view of a head blend for 3DDFA (replica of render_front_for_3ddfa.py, parameterized).

Usage: blender -b --factory-startup -noaudio --python-exit-code 1 --python render_front.py -- <IN_BLEND> <OUT_DIR>
Outputs: <OUT_DIR>/face_front.png (1024x1024) + cam_params.json
Faithful to the original camera rig: ORTHO scale 0.40, aim_z = bbox 88% height, Workbench TEXTURE.
"""
import bpy, os, sys, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
IN_BLEND, OUT_DIR = argv[0], argv[1]
OUT_PNG = os.path.join(OUT_DIR, "face_front.png")
OUT_CAM = os.path.join(OUT_DIR, "cam_params.json")

RES = 1024
ORTHO_SCALE = 0.40
CAM_DIST = 0.5

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]

    vs = obj.data.vertices
    xs = [v.co.x for v in vs]; ys = [v.co.y for v in vs]; zs = [v.co.z for v in vs]
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2
    aim_z = min(zs) + (max(zs)-min(zs))*0.88
    aim = Vector((cx, cy, aim_z))

    cam_data = bpy.data.cameras.new("3DDFA_Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ORTHO_SCALE
    cam_data.clip_start = 0.01
    cam_data.clip_end = 5.0
    cam = bpy.data.objects.new("3DDFA_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)

    cam_pos = Vector((cx, aim.y - CAM_DIST, aim.z))
    cam.location = cam_pos
    look = aim - cam_pos
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()

    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_specular_highlight = False

    scene.render.filepath = OUT_PNG
    bpy.ops.render.render(write_still=True)
    print(f"rendered: {OUT_PNG}")

    R = cam.matrix_world
    forward = (R @ Vector((0, 0, -1)) - R @ Vector((0, 0, 0))).normalized()
    right = (R @ Vector((1, 0, 0)) - R @ Vector((0, 0, 0))).normalized()
    up = (R @ Vector((0, 1, 0)) - R @ Vector((0, 0, 0))).normalized()
    params = {
        "cam_location": list(cam.location),
        "forward": list(forward),
        "right": list(right),
        "up": list(up),
        "ortho_scale": ORTHO_SCALE,
        "res_x": RES, "res_y": RES,
        "wpp": ORTHO_SCALE / RES,
        "aim": list(aim),
    }
    with open(OUT_CAM, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    print(f"cam params: {OUT_CAM}")
    print(f"wpp={params['wpp']*1000:.4f} mm/pixel")
    print("=== Done ===")

main()
