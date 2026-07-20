"""Render checkerboard on UV to visually verify quality.
Uses CONFORMAL (fast, 3s) with the minimal seams that gave 84 islands.
"""
import bpy, bmesh, math, json, time, os

def find_mesh():
    for o in bpy.data.objects:
        if o.type == 'MESH' and 'Retopo' in o.name:
            return o
    for o in bpy.data.objects:
        if o.type == 'MESH':
            return o
    return None

def clear_seams(mesh):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

def count_islands(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh.data); bm.faces.ensure_lookup_table()
    visited=set(); islands=0
    for f in bm.faces:
        if f.index in visited: continue
        stack=[f]
        while stack:
            cf=stack.pop()
            if cf.index in visited: continue
            visited.add(cf.index)
            for e in cf.edges:
                if not e.seam:
                    for lf in e.link_faces:
                        if lf.index not in visited: stack.append(lf)
        islands+=1
    bm.free(); return islands

def mark_seams(mesh):
    bm=bmesh.new(); bm.from_mesh(mesh.data)
    xs=[v.co.x for v in bm.verts]; ys=[v.co.y for v in bm.verts]; zs=[v.co.z for v in bm.verts]
    min_x,max_x=min(xs),max(xs); min_z,max_z=min(zs),max(zs)
    mid_x=(min_x+max_x)/2; H=max_z-min_z; W=max_x-min_x
    xt=W*0.0015; xt_leg=W*0.002
    seams=0; st={'back':0,'armL':0,'armR':0,'legL':0,'legR':0}
    for e in bm.edges:
        v0,v1=e.verts; m=(v0.co+v1.co)/2
        if abs(v0.co.x-mid_x)<xt and abs(v1.co.x-mid_x)<xt \
           and v0.co.y>0 and v1.co.y>0 and min_z+H*0.05<m.z<min_z+H*0.95:
            e.seam=True; seams+=1; st['back']+=1; continue
        # ARM seams DISABLED — prior test showed arm conditions catch too many edges
        # (4596 seams → 2301 islands). Use only back+leg for 455 seams/84 islands.
        if False and v0.co.x<mid_x-W*0.15 and v1.co.x<mid_x-W*0.15 \
           and v0.co.y<0 and v1.co.y<0 and min_z+H*0.55<m.z<min_z+H*0.88:
            e.seam=True; seams+=1; st['armL']+=1; continue
        if False and v0.co.x>mid_x+W*0.15 and v1.co.x>mid_x+W*0.15 \
           and v0.co.y<0 and v1.co.y<0 and min_z+H*0.55<m.z<min_z+H*0.88:
            e.seam=True; seams+=1; st['armR']+=1; continue
        if min_z+H*0.05<m.z<min_z+H*0.45 \
           and abs(v0.co.x-(mid_x-W*0.015))<xt_leg and abs(v1.co.x-(mid_x-W*0.015))<xt_leg \
           and v0.co.y<0 and v1.co.y<0:
            e.seam=True; seams+=1; st['legL']+=1; continue
        if min_z+H*0.05<m.z<min_z+H*0.45 \
           and abs(v0.co.x-(mid_x+W*0.015))<xt_leg and abs(v1.co.x-(mid_x+W*0.015))<xt_leg \
           and v0.co.y<0 and v1.co.y<0:
            e.seam=True; seams+=1; st['legR']+=1; continue
    bm.to_mesh(mesh.data); bm.free()
    return seams, st

def setup_checker_material(mesh):
    """Create a checkerboard material that uses UV coordinates."""
    mat = bpy.data.materials.new(name="UVChecker")
    mesh.data.materials.clear()
    mesh.data.materials.append(mat)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    # Checker texture driven by UV
    checker = nodes.new('ShaderNodeTexChecker')
    checker.inputs['Scale'].default_value = 8.0
    # UV map node
    uvmap = nodes.new('ShaderNodeUVMap')
    links.new(uvmap.outputs['UV'], checker.inputs['Vector'])
    links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

def render_view(mesh, output_path, camera_loc=(0,-3,1), camera_rot=(1.4,0,0)):
    """Render a viewport-style image of the mesh."""
    # Add camera
    cam_data = bpy.data.cameras.new("TestCam")
    cam = bpy.data.objects.new("TestCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = camera_loc
    cam.rotation_euler = camera_rot
    bpy.context.scene.camera = cam
    # Render settings
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = output_path
    # Lighting
    light_data = bpy.data.lights.new("Light", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("Light", light_data)
    bpy.context.collection.objects.link(light)
    light.location = (2,-2,3)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

def main():
    mesh = find_mesh()
    if not mesh:
        print("ERROR: no mesh"); return
    print(f"Mesh: {mesh.name} | faces={len(mesh.data.polygons)}")
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    if not mesh.data.uv_layers: mesh.data.uv_layers.new(name='UVMap')
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]
    clear_seams(mesh)
    seams, st = mark_seams(mesh)
    pre = count_islands(mesh)
    print(f"seams={seams} {st} pre_islands={pre}")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    t0=time.time()
    bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=True, correct_aspect=True,
                      margin_method='SCALED', margin=0.003)
    t1=time.time()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='SCALED', margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"unwrap={t1-t0:.1f}s")
    setup_checker_material(mesh)
    out_dir = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test03_SimplifiedPipeline\v5_run"
    # Front view
    render_view(mesh, os.path.join(out_dir, "uv_check_front.png"),
                camera_loc=(0,-3,1.0), camera_rot=(1.45,0,0))
    # Back view
    render_view(mesh, os.path.join(out_dir, "uv_check_back.png"),
                camera_loc=(0,3,1.0), camera_rot=(1.45,0,3.14159))
    # Save blend
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "03_remesh_uv_conformal.blend"))
    print("=== DONE ===")

if __name__ == '__main__':
    main()

