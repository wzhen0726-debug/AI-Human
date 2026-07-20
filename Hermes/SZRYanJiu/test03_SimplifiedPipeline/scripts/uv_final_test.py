"""Final optimized UV test: minimal seams + MINIMUM_STRETCH + render checkerboard.
Target: <50 islands, no stretching, texel density uniform.
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
    visited = set(); islands = 0
    for f in bm.faces:
        if f.index in visited: continue
        stack = [f]
        while stack:
            cf = stack.pop()
            if cf.index in visited: continue
            visited.add(cf.index)
            for e in cf.edges:
                if not e.seam:
                    for lf in e.link_faces:
                        if lf.index not in visited: stack.append(lf)
        islands += 1
    bm.free()
    return islands

def mark_optimized_seams(mesh):
    """Optimized anatomical seams. Prior test: back_center(268)+leg_L(95)+leg_R(92)=455 seams, 84 islands.
    Add arm inner seams (Y<0, longitudinal) to split arms from body → fewer islands."""
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    xs=[v.co.x for v in bm.verts]; ys=[v.co.y for v in bm.verts]; zs=[v.co.z for v in bm.verts]
    min_x,max_x=min(xs),max(xs); min_y,max_y=min(ys),max(ys); min_z,max_z=min(zs),max(zs)
    mid_x=(min_x+max_x)/2; H=max_z-min_z; W=max_x-min_x; D=max_y-min_y
    xt=W*0.0015; xt_leg=W*0.002; xt_arm=W*0.02
    print(f"  bbox: W={W:.3f} D={D:.3f} H={H:.3f}")
    seams=0; st={'back_center':0,'arm_inner_L':0,'arm_inner_R':0,'leg_L':0,'leg_R':0}
    for e in bm.edges:
        v0,v1=e.verts; m=(v0.co+v1.co)/2
        # 1. Back center line
        if abs(v0.co.x-mid_x)<xt and abs(v1.co.x-mid_x)<xt \
           and v0.co.y>0 and v1.co.y>0 \
           and min_z+H*0.05<m.z<min_z+H*0.95:
            e.seam=True; seams+=1; st['back_center']+=1; continue
        # 2. Left arm inner (Y<0 front, Z 0.55-0.88H, X<-0.15W)
        if v0.co.x<mid_x-W*0.15 and v1.co.x<mid_x-W*0.15 \
           and v0.co.y<0 and v1.co.y<0 \
           and min_z+H*0.55<m.z<min_z+H*0.88 \
           and abs(v0.co.y-v1.co.y)<D*0.05:
            e.seam=True; seams+=1; st['arm_inner_L']+=1; continue
        # 3. Right arm inner
        if v0.co.x>mid_x+W*0.15 and v1.co.x>mid_x+W*0.15 \
           and v0.co.y<0 and v1.co.y<0 \
           and min_z+H*0.55<m.z<min_z+H*0.88 \
           and abs(v0.co.y-v1.co.y)<D*0.05:
            e.seam=True; seams+=1; st['arm_inner_R']+=1; continue
        # 4. Left leg inner
        if min_z+H*0.05<m.z<min_z+H*0.45 \
           and abs(v0.co.x-(mid_x-W*0.015))<xt_leg \
           and abs(v1.co.x-(mid_x-W*0.015))<xt_leg \
           and v0.co.y<0 and v1.co.y<0:
            e.seam=True; seams+=1; st['leg_L']+=1; continue
        # 5. Right leg inner
        if min_z+H*0.05<m.z<min_z+H*0.45 \
           and abs(v0.co.x-(mid_x+W*0.015))<xt_leg \
           and abs(v1.co.x-(mid_x+W*0.015))<xt_leg \
           and v0.co.y<0 and v1.co.y<0:
            e.seam=True; seams+=1; st['leg_R']+=1; continue
    bm.to_mesh(mesh.data); bm.free()
    print(f"  seam types: {st}")
    return seams, st

def run_final(method='MINIMUM_STRETCH', iterations=20, render=True):
    mesh = find_mesh()
    if not mesh: return {'error':'no mesh'}
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    if not mesh.data.uv_layers: mesh.data.uv_layers.new(name='UVMap')
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]
    clear_seams(mesh)
    seams, st = mark_optimized_seams(mesh)
    pre_islands = count_islands(mesh)
    print(f"  seams={seams} pre_unwrap_islands={pre_islands}")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    t0=time.time()
    kwargs=dict(method=method, fill_holes=True, correct_aspect=True,
                margin_method='SCALED', margin=0.003)
    if method=='MINIMUM_STRETCH': kwargs['iterations']=iterations
    bpy.ops.uv.unwrap(**kwargs)
    t1=time.time()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='SCALED', margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    t2=time.time()
    # Count UV islands after unwrap (via UV island flood fill)
    bm=bmesh.new(); bm.from_mesh(mesh.data); bm.faces.ensure_lookup_table()
    uv=mesh.data.uv_layers.active
    # build adjacency via UV (loops with same UV coord are connected)
    # simpler: count via python UV-linked faces
    visited=set(); islands=0
    loop_uv={}
    for f in bm.faces:
        for l in f.loops:
            li=l.index
            v=uv.data[li].uv
            loop_uv[li]=(round(v.x,5), round(v.y,5))
    bm.free()
    return {
        'method':method, 'seams':seams, 'seam_types':st,
        'pre_unwrap_islands':pre_islands,
        'unwrap_time_s':round(t1-t0,2), 'total_time_s':round(t2-t0,2),
    }

if __name__=='__main__':
    mesh=find_mesh()
    print(f"Mesh: {mesh.name if mesh else 'NONE'} | faces={len(mesh.data.polygons) if mesh else 0}")
    print("\n--- FINAL: MINIMUM_STRETCH + optimized seams ---")
    r=run_final('MINIMUM_STRETCH', 20)
    print(f"RESULT: {json.dumps(r, default=str)}")
    # Save blend
    out=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test03_SimplifiedPipeline\v5_run\03_remesh_final_uv.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"Saved: {out}")
    print("=== DONE ===")

