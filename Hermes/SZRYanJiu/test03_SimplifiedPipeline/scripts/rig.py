"""
Stage 7: 绑定 — Auto-Rig Pro Smart自动绑定.
Blender 5.1 background script.

修复：
1. 移除旋转代码（repair阶段已做）
2. fix_marker_positions从body_temp几何精确计算关节位置
3. 所有标记确保在网格范围内
"""
import bpy, sys, json, argparse, os, time, math, random, subprocess
from mathutils import Vector


def get_retopo_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    meshes = [(o, len(o.data.polygons)) for o in bpy.data.objects if o.type == 'MESH']
    if meshes:
        meshes.sort(key=lambda x: x[1])
        return meshes[0][0]
    return None


def enable_arp():
    try:
        bpy.ops.preferences.addon_enable(module='auto_rig_pro-master')
        print("ARP addon enabled")
    except Exception as e:
        print(f"ARP enable failed: {e}")
    prefs = bpy.context.preferences.addons.get('auto_rig_pro-master')
    if prefs and hasattr(prefs, 'preferences'):
        ai_path = r'C:/Users/Liyunzhong/Documents/AutoRigPro/AI'
        prefs.preferences.ai_presets_path = ai_path
        print(f"ARP AI path set to: {ai_path}")


def find_view3d_area():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            return area
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                bpy.context.window.screen = screen
                return area
    return None


def patch_arp_for_background():
    """Patch ARP functions for background mode."""
    import sys
    ars = None
    for key, mod in sys.modules.items():
        if 'auto_rig_smart' in key and hasattr(mod, '_screenshot_char'):
            ars = mod
            break
    if not ars:
        print("ERROR: Could not find auto_rig_smart module")
        return False

    ara = None
    for key, mod in sys.modules.items():
        if 'auto_rig' in key and hasattr(mod, 'display_popup_message'):
            ara = mod
            break
    if ara:
        ara.display_popup_message = lambda msg, header=' ', icon_type='': print(f"[ARP {header}] {msg}")
        print("display_popup_message patched")

    def screenshot_patched(self):
        body_temp = bpy.data.objects.get('body_temp')
        scn = bpy.context.scene
        bpy.context.view_layer.objects.active = body_temp
        bbox = [body_temp.matrix_world @ Vector(c) for c in body_temp.bound_box]
        x1, x2 = bbox[0][0], bbox[4][0]
        y1, y2 = bbox[0][1], bbox[6][1]
        z1, z2 = bbox[0][2], bbox[2][2]
        dim_x = abs(x2-x1); dim_y = abs(y2-y1); dim_z = abs(z2-z1)
        self.larger_dim = max(dim_x, dim_z)
        self.larger_dimy = max(dim_y, dim_z)
        self.larger_dimtop = max(dim_y, dim_x)
        self.midx = (x1+x2)*0.5; self.midy = (y1+y2)*0.5; self.midz = (z1+z2)*0.5

        cam_data = bpy.data.cameras.new('arp_cam')
        cam_obj = bpy.data.objects.new('arp_cam', cam_data)
        bpy.context.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj
        cam_obj.data.type = 'ORTHO'; cam_obj.data.clip_end = 50000
        margin = 1.05

        gray_mat = bpy.data.materials.new('ARP_Gray')
        gray_mat.use_nodes = True
        bsdf = gray_mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
        bsdf.inputs['Roughness'].default_value = 0.5
        old_mats = body_temp.data.materials[:]
        body_temp.data.materials.clear()
        body_temp.data.materials.append(gray_mat)

        if scn.world:
            scn.world.use_nodes = True
            bg = scn.world.node_tree.nodes.get('Background')
            bg.inputs['Color'].default_value = (0.04, 0.04, 0.04, 1)
            bg.inputs['Strength'].default_value = 1.0

        scn.render.engine = 'CYCLES'; scn.cycles.samples = 1
        scn.render.resolution_x = 256; scn.render.resolution_y = 256
        scn.render.image_settings.file_format = 'JPEG'
        scn.render.image_settings.color_mode = 'RGB'

        cam_obj.location = (self.midx, y1-dim_y*10, self.midz)
        cam_obj.rotation_euler = (math.pi/2, 0, 0)
        cam_obj.data.ortho_scale = self.larger_dim * margin

        picked = [0]; self.front_samples_rot = []
        for i in range(1, scn.arp_smart_AI_body_samples+1):
            roty = 0
            if i != 1:
                a = random.randint(-15, 15)
                while a in picked: a = random.randint(-15, 15)
                picked.append(a); roty = math.radians(a)
                cam_obj.data.ortho_scale *= 1.1
            cam_obj.rotation_euler[1] = roty
            self.front_samples_rot.append(roty)
            save_path = os.path.join(self.inf_path, f'front{i}.jpg')
            scn.render.filepath = bpy.path.abspath(save_path)
            bpy.ops.render.render(write_still=True)

        cam_obj.location = (x2+dim_x*10, self.midy, self.midz)
        cam_obj.rotation_euler = [math.pi/2, 0, math.pi/2]
        cam_obj.data.ortho_scale = self.larger_dimy * margin
        scn.render.filepath = bpy.path.abspath(os.path.join(self.inf_path, 'char_side.jpg'))
        bpy.ops.render.render(write_still=True)

        cam_obj.location = (self.midx, self.midy, z2+dim_z*10)
        cam_obj.rotation_euler = [0, 0, 0]
        cam_obj.data.ortho_scale = self.larger_dimtop * margin
        scn.render.filepath = bpy.path.abspath(os.path.join(self.inf_path, 'char_top.jpg'))
        bpy.ops.render.render(write_still=True)

        bpy.data.objects.remove(cam_obj)
        body_temp.data.materials.clear()
        for m in old_mats:
            if m: body_temp.data.materials.append(m)
        bpy.data.materials.remove(gray_mat)

    ars._screenshot_char = screenshot_patched
    print("_screenshot_char patched")
    return True


def fix_marker_positions():
    """Override marker positions using body_temp mesh geometry.
    All positions are clamped to be inside the mesh bounding box.
    """
    body_temp = bpy.data.objects.get('body_temp')
    if not body_temp:
        print("fix_marker_positions: body_temp not found")
        return

    mesh = body_temp.data
    verts = mesh.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    H = max_z - min_z  # height

    # Clamp helper: keep inside mesh bbox with small margin
    def clamp(val, lo, hi, m=0.02):
        return max(lo + m, min(hi - m, val))

    def set_marker(name, x, y, z):
        o = bpy.data.objects.get(name)
        if o:
            cx = clamp(x, min_x, max_x)
            cy = clamp(y, min_y, max_y)
            cz = clamp(z, min_z, max_z)
            o.location = (cx, cy, cz)
            print(f"  {name}: ({cx:.3f}, {cy:.3f}, {cz:.3f})")

    # For each body part, find the average position of vertices in that Z-band
    # and use the center X/Y. This ensures markers are ON the mesh surface.
    def find_band_center(z_lo, z_hi, x_filter=None):
        """Find center of vertices in a Z height band."""
        band = [v for v in verts if z_lo <= v.co.z <= z_hi]
        if x_filter:
            band = [v for v in band if x_filter(v.co.x)]
        if not band:
            return mid_x, mid_y
        bx = sum(v.co.x for v in band) / len(band)
        by = sum(v.co.y for v in band) / len(band)
        return bx, by

    # Root (pelvis): center at ~42% height
    z = min_z + H * 0.42
    bx, by = find_band_center(z - H*0.02, z + H*0.02)
    set_marker('root_loc', bx, by, z)

    # Neck: center at ~87% height
    z = min_z + H * 0.87
    bx, by = find_band_center(z - H*0.015, z + H*0.015)
    set_marker('neck_loc', bx, by, z)

    # Chin: center at ~90% height
    z = min_z + H * 0.90
    bx, by = find_band_center(z - H*0.01, z + H*0.01)
    set_marker('chin_loc', bx, by, z)

    # Shoulders: at ~80% height
    # Right shoulder: max X in that band
    z = min_z + H * 0.80
    band = [v for v in verts if abs(v.co.z - z) < H*0.025]
    if band:
        right_x = max(v.co.x for v in band)
        left_x = min(v.co.x for v in band)
        right_y = sum(v.co.y for v in band if v.co.x > mid_x) / max(1, len([v for v in band if v.co.x > mid_x]))
        left_y = sum(v.co.y for v in band if v.co.x < mid_x) / max(1, len([v for v in band if v.co.x < mid_x]))
    else:
        right_x = max_x * 0.35; left_x = min_x * 0.35
        right_y = mid_y; left_y = mid_y
    set_marker('shoulder_loc', right_x, right_y, z)
    set_marker('shoulder_loc_sym', left_x, left_y, z)

    # Elbows: at ~55% height, at 65% of max X
    z = min_z + H * 0.55
    bx_r, by_r = find_band_center(z - H*0.02, z + H*0.02, lambda x: x > max_x * 0.4)
    bx_l, by_l = find_band_center(z - H*0.02, z + H*0.02, lambda x: x < min_x * 0.4)
    set_marker('elbow_loc', bx_r or max_x*0.65, by_r, z)
    set_marker('elbow_loc_sym', bx_l or min_x*0.65, by_l, z)

    # Hands: at ~58% height (T-pose, hands at shoulder level), at 85% max X
    z = min_z + H * 0.58
    bx_r, by_r = find_band_center(z - H*0.02, z + H*0.02, lambda x: x > max_x * 0.6)
    bx_l, by_l = find_band_center(z - H*0.02, z + H*0.02, lambda x: x < min_x * 0.6)
    set_marker('hand_loc', bx_r or max_x*0.85, by_r, z)
    set_marker('hand_loc_sym', bx_l or min_x*0.85, by_l, z)

    # Hand tips: at ~58% height, at 92% max X
    set_marker('hand_tip_loc', max_x * 0.92, mid_y, z)
    set_marker('hand_tip_loc_sym', min_x * 0.92, mid_y, z)

    # Thighs: at ~38% height, offset from center
    z = min_z + H * 0.38
    band = [v for v in verts if abs(v.co.z - z) < H*0.02]
    if band:
        right_thigh_x = mid_x + (max_x - min_x) * 0.08
        left_thigh_x = mid_x - (max_x - min_x) * 0.08
        thigh_y = sum(v.co.y for v in band) / len(band)
    else:
        right_thigh_x = mid_x + 0.03; left_thigh_x = mid_x - 0.03
        thigh_y = mid_y
    set_marker('thigh_loc', right_thigh_x, thigh_y, z)
    set_marker('thigh_loc_sym', left_thigh_x, thigh_y, z)

    # Knees: at ~22% height
    z = min_z + H * 0.22
    bx_r, by_r = find_band_center(z - H*0.02, z + H*0.02, lambda x: x > mid_x + 0.01)
    bx_l, by_l = find_band_center(z - H*0.02, z + H*0.02, lambda x: x < mid_x - 0.01)
    set_marker('knee_loc', bx_r or mid_x+0.03, by_r, z)
    set_marker('knee_loc_sym', bx_l or mid_x-0.03, by_l, z)

    # Feet: at ~3% height
    z = min_z + H * 0.03
    bx_r, by_r = find_band_center(z - H*0.02, z + H*0.02, lambda x: x > mid_x)
    bx_l, by_l = find_band_center(z - H*0.02, z + H*0.02, lambda x: x < mid_x)
    set_marker('foot_loc', bx_r or mid_x+0.02, by_r, z)
    set_marker('foot_loc_sym', bx_l or mid_x-0.02, by_l, z)

    print("  All markers fixed from mesh geometry")


def arp_smart_rig(mesh_obj):
    """Run ARP Smart auto-rigging on the mesh."""
    stats = {"mesh": mesh_obj.name, "verts": len(mesh_obj.data.vertices)}

    area = find_view3d_area()
    if not area:
        stats["error"] = "No VIEW_3D area found"
        return stats
    region = None
    for r in area.regions:
        if r.type == 'WINDOW':
            region = r
            break
    if not region:
        stats["error"] = "No WINDOW region"
        return stats

    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    patch_arp_for_background()

    with bpy.context.temp_override(area=area, region=region):
        bpy.context.scene.arp_smart_type = 'BODY'

        print("ARP Step 1: get_selected_objects...")
        try:
            bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
            print("  done")
        except Exception as e:
            stats["error"] = f"get_selected_objects: {e}"
            return stats

        print("ARP Step 2: guess_markers...")
        try:
            bpy.ops.arp.guess_markers('EXEC_DEFAULT')
            print("  done")
        except Exception as e:
            stats["error"] = f"guess_markers: {e}"
            return stats

        # Fix markers from geometry
        fix_marker_positions()

        print("ARP Step 3: go_detect...")
        bpy.context.scene.arp_smart_depth = False
        try:
            bpy.ops.id.go_detect('EXEC_DEFAULT')
            print("  done")
        except Exception as e:
            stats["error"] = f"go_detect: {e}"
            return stats

    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    stats["armatures"] = len(arms)
    if arms:
        arm = arms[0]
        stats["armature_name"] = arm.name
        stats["bone_count"] = len(arm.data.bones)
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.vertex_groups:
                stats["vertex_groups"] = len(o.vertex_groups)
                stats["rigged_mesh"] = o.name
                break
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    enable_arp()
    if 'Layout' in bpy.data.screens:
        bpy.context.window.screen = bpy.data.screens['Layout']

    mesh = get_retopo_mesh()
    if not mesh:
        print("ERROR: No mesh found")
        sys.exit(1)

    print(f"Rigging: {mesh.name} ({len(mesh.data.vertices)} verts)")
    result = arp_smart_rig(mesh)
    print("Rig Result:", json.dumps(result, indent=2))

    if args.output:
        bpy.ops.wm.save_as_mainfile(filepath=args.output)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
