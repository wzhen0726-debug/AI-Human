import bpy, os, subprocess, tempfile, time
import bmesh

# === 配置 ===
HIGH_POLY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\tripoTpose_01_repair.blend"
OUT_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02\mvp_pipeline\output"
os.makedirs(OUT_DIR, exist_ok=True)

QR_ENGINE = r"C:\Users\Liyunzhong\AppData\Roaming\Blender Foundation\Blender\5.1\extensions\user_default\quadremesher\EngineWin\xremesh.exe"
QR_TEMP = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")
os.makedirs(QR_TEMP, exist_ok=True)

# === Step 1: 加载高模 ===
print("=== Step 1: 加载高模 ===")
bpy.ops.wm.open_mainfile(filepath=HIGH_POLY)
high_poly = [o for o in bpy.data.objects if o.type == 'MESH'][0]
print(f"高模: {high_poly.name}, {len(high_poly.data.polygons)}面")

# === Step 1.5: 说明 ===
# 策略：提高目标面数到150K + adaptive_size=80%，让高曲率区域（面部/手部）自动分配更多面
# 不拆分头部/手部，保持整体拓扑

input_fbx = os.path.join(QR_TEMP, "inputMesh.fbx")
bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
bpy.context.view_layer.objects.active = high_poly

print("导出FBX...")
bpy.ops.export_scene.fbx(
    filepath=input_fbx, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='OFF', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)

# === Step 2: 调用xremesh ===
print("\n=== Step 2: Quad Remesher ===")
settings_file = os.path.join(QR_TEMP, "RetopoSettings.txt")
retopo_fbx = os.path.join(QR_TEMP, "retopo.fbx")
progress_file = os.path.join(QR_TEMP, "progress.txt")

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
    f.write('UseVertexColorMap=0\n')  # 顶点色不生效，关闭
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\n')

print("调用xremesh.exe (目标90K面)...")
proc = subprocess.Popen([QR_ENGINE, "-s", settings_file],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

start_time = time.time()
while time.time() - start_time < 900:
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
    print("错误: retopo.fbx未生成")
    exit(1)

print(f"QR完成: {os.path.getsize(retopo_fbx)/1024/1024:.1f}MB")

# === Step 3: 导入QR结果并清理 ===
print("\n=== Step 3: 导入并清理 ===")

# 新建空场景
bpy.ops.wm.read_factory_settings(use_empty=True)

# 导入retopo.fbx
bpy.ops.import_scene.fbx(filepath=retopo_fbx)
# 获取导入的mesh（可能是多个，取第一个）
imported = [o for o in bpy.data.objects if o.type == 'MESH']
if not imported:
    print("错误: 导入后无mesh")
    exit(1)
qr_obj = imported[0]
print(f"QR低模: {qr_obj.name}, {len(qr_obj.data.polygons)}面, {len(qr_obj.data.vertices)}顶点")

# 重命名为简洁名称
qr_obj.name = "MVP_LowPoly"

# 检查UV
if qr_obj.data.uv_layers:
    print(f"UV层: {len(qr_obj.data.uv_layers)}")
else:
    print("无UV层")

# 检查法线
import bmesh
bm = bmesh.new()
bm.from_mesh(qr_obj.data)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
print(f"非流形边: {non_manifold}")

# 保存blend
blend_path = os.path.join(OUT_DIR, "02_qr_lowpoly.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"已保存: {blend_path}")

# 导出FBX供检查
fbx_path = os.path.join(OUT_DIR, "02_qr_lowpoly.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_path, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=False, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='AUTO'
)
print(f"已导出: {fbx_path}")

print("DONE")
