#!/usr/bin/env python3
"""Batch runner: runs the full pipeline N times, records results."""
import subprocess, json, os, sys, time, shutil

BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test03_SimplifiedPipeline"
GLB_IN = os.path.join(BASE, "input", "raw_model.glb")
SCRIPTS = os.path.join(BASE, "scripts")
QR_TEMP = r"C:\Users\Liyunzhong\AppData\Local\Temp\Exoside\QuadRemesher\Blender"

def run_blender(script, blend_in, extra_args, timeout=300):
    cmd = [BLENDER, blend_in, "--background", "--factory-startup",
           "--python", script, "--"] + extra_args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def run_round(n):
    out = os.path.join(BASE, "output")
    rd = os.path.join(BASE, f"run_{n}")
    os.makedirs(rd, exist_ok=True)
    log = []
    
    # Stage 1: Import GLB + repair
    r1 = os.path.join(rd, "01_repair.blend")
    cmd = [BLENDER, "--background", "--factory-startup", "--python-expr",
           f"import bpy; bpy.ops.import_scene.gltf(filepath=r'{GLB_IN}'); "
           f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import repair; obj=repair.get_main_mesh(); "
           f"r=repair.repair_pipeline(obj,0.005,5,0.5); "
           f"print('REPAIR:'+str(len(obj.data.vertices))); "
           f"bpy.ops.wm.save_as_mainfile(filepath=r'{r1}')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.append(f"repair: rc={rc} out={stdout[-200:] if stdout else ''}")
    
    # Stage 2: Adhesion
    r2 = os.path.join(rd, "02_adhesion.blend")
    cmd = [BLENDER, r1, "--background", "--factory-startup", "--python-expr",
           f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import adhesion; obj=adhesion.get_main_mesh(); "
           f"pairs=adhesion.detect_adhesion(obj); "
           f"print(f'ADHESION: {len(pairs)} pairs'); "
           f"if pairs: adhesion.fix_adhesion(obj, pairs); "
           f"bpy.ops.wm.save_as_mainfile(filepath=r'{r2}')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.append(f"adhesion: rc={rc} pairs={stdout}")
    
    # Stage 3: Quad Remesher (async)
    r3 = os.path.join(rd, "03_remesh.blend")
    cmd = [BLENDER, r2, "--background", "--python-expr",
           f"import sys,os,time; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import remesh; obj=remesh.get_main_mesh(); "
           f"r=remesh.quad_remesh(obj,250000,False,True,50.0); "
           f"print('REMESH:'+str(r.get('retopo_verts','?'))); "
           f"bpy.ops.wm.save_as_mainfile(filepath=r'{r3}')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log.append(f"remesh: rc={rc}")
    
    # Stage 4: UV
    r4 = os.path.join(rd, "04_uv.blend")
    cmd = [BLENDER, r3, "--background", "--factory-startup", "--python-expr",
           f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import uv; meshes=[(o,len(o.data.vertices)) for o in bpy.data.objects if o.type=='MESH']; "
           f"meshes.sort(key=lambda x:x[1],reverse=True); "
           f"r=uv.auto_uv_pipeline(meshes[0][0]); "
           f"print(f'UV: {r[\"total_seams\"]} seams'); "
           f"bpy.ops.wm.save_as_mainfile(filepath=r'{r4}')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.append(f"uv: rc={rc}")
    
    # Stage 5: Bake
    r5 = os.path.join(rd, "05_bake.blend")
    cmd = [BLENDER, r4, "--background", "--factory-startup", "--python-expr",
           f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import bake; bpy.ops.import_scene.gltf(filepath=r'{GLB_IN}'); "
           f"for o in list(bpy.data.objects): "
           f"  if o.type=='MESH' and len(o.data.vertices)<100: bpy.data.objects.remove(o,do_unlink=True); "
           f"all_m=[(o,len(o.data.polygons)) for o in bpy.data.objects if o.type=='MESH']; "
           f"all_m.sort(key=lambda x:x[1],reverse=True); "
           f"high=all_m[0][0]; low=[o for o in bpy.data.objects if 'Retopo' in o.name][0]; "
           f"r=bake.bake_textures(low,high,2048,0.05,0.02); "
           f"print(f'BAKE: {list(r.get(\"bake_results\", {}).keys())}'); "
           f"bpy.ops.wm.save_as_mainfile(filepath=r'{r5}')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log.append(f"bake: rc={rc}")
    
    # Stage 6: GLB Export
    r6 = os.path.join(rd, "final.glb")
    cmd = [BLENDER, r5, "--background", "--factory-startup", "--python-expr",
           f"import sys; sys.path.insert(0, r'{SCRIPTS}'); "
           f"import export_glb; r=export_glb.export_glb(r'{r6}'); "
           f"print(f'GLB: {r.get(\"file_size_mb\",\"?\")}MB')"]
    stdout, stderr, rc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.append(f"glb: rc={rc}")
    
    return log

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for i in range(1, n+1):
        print(f"\n{'='*40}\nRUN {i}/{n}\n{'='*40}")
        t0 = time.time()
        log = run_round(i)
        elapsed = time.time() - t0
        print(f"Run {i} done in {elapsed:.0f}s")
        for l in log:
            print(f"  {l}")