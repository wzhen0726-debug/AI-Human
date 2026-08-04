import bpy, os, subprocess, tempfile, time

OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\mvp_pipeline\output"
QR_ENGINE = r"C:\Users\Liyunzhong\AppData\Roaming\Blender Foundation\Blender\5.1\extensions\user_default\quadremesher\EngineWin\xremesh.exe"
QR_TEMP = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")

print("=== 方案1: Decimate预处理 + QR ===")

# 加载预处理后的模型
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "01_decimate_pre_qr.blend"))
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"预处理模型: {len(mesh.data.polygons)}面")

# 导出FBX
input_fbx = os.path.join(QR_TEMP, "inputMesh_decimate.fbx")
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.export_scene.fbx(
    filepath=input_fbx, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='OFF', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)

# QR设置
settings_file = os.path.join(QR_TEMP, "RetopoSettings_decimate.txt")
retopo_fbx = os.path.join(QR_TEMP, "retopo_decimate.fbx")
progress_file = os.path.join(QR_TEMP, "progress_decimate.txt")

for f in [retopo_fbx, progress_file]:
    if os.path.exists(f): os.remove(f)

with open(settings_file, 'w') as f:
    f.write('HostApp=Blender\n')
    f.write(f'FileIn="{input_fbx}"\n')
    f.write(f'FileOut="{retopo_fbx}"\n')
    f.write(f'ProgressFile="{progress_file}"\n')
    f.write('TargetQuadCount=150000\n')
    f.write('CurvatureAdaptivness=80\n')
    f.write('ExactQuadCount=0\n')
    f.write('UseVertexColorMap=0\n')
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\n')

print("调用xremesh (目标150K)...")
proc = subprocess.Popen([QR_ENGINE, "-s", settings_file],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

start = time.time()
while time.time() - start < 900:
    if os.path.exists(retopo_fbx):
        time.sleep(2)
        break
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            p = f.read().strip()
            if p: print(f"  进度: {p}")
    time.sleep(5)

proc.terminate()
try: proc.wait(timeout=5)
except: proc.kill()

if not os.path.exists(retopo_fbx):
    print("错误: QR未完成")
    exit(1)

# 导入结果
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=retopo_fbx)
qr = [o for o in bpy.data.objects if o.type == 'MESH'][0]
qr.name = "MVP_LowPoly_v1"

print(f"QR结果: {len(qr.data.polygons)}面")

# 验证
import bmesh
bm = bmesh.new()
bm.from_mesh(qr.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
quads = sum(1 for p in qr.data.polygons if len(p.vertices) == 4)
bm.free()

print(f"quad: {quads/len(qr.data.polygons)*100:.1f}%")
print(f"非流形边: {non_manifold}")

# 区域分布
head = hand = other = 0
for p in qr.data.polygons:
    vs = [qr.data.vertices[i] for i in p.vertices]
    avg_z = sum(v.co.z for v in vs) / len(vs)
    max_x = max(abs(v.co.x) for v in vs)
    if avg_z > 0.8: head += 1
    elif max_x > 0.35 and avg_z > 0.7: hand += 1
    else: other += 1

print(f"头部: {head} ({head/len(qr.data.polygons)*100:.1f}%)")
print(f"手部: {hand} ({hand/len(qr.data.polygons)*100:.1f}%)")
print(f"其他: {other} ({other/len(qr.data.polygons)*100:.1f}%)")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "02_qr_v1_decimate.blend"))
fbx_out = os.path.join(OUT_DIR, "02_qr_v1_decimate.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_out, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"已保存: 02_qr_v1_decimate.blend/fbx")
print("DONE")
