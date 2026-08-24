import bpy, os, sys, subprocess, tempfile, time

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
OUT_02 = os.path.join(DELIVERY, "02QuadRemesher拓扑")
os.makedirs(OUT_02, exist_ok=True)

# QR引擎路径
APPDATA = os.environ.get('APPDATA', '')
QR_EXT = os.path.join(APPDATA, "Blender Foundation", "Blender", "5.1", "extensions", "user_default", "quadremesher")
ENGINE = os.path.join(QR_EXT, "EngineWin", "xremesh.exe")

# 临时目录
QRTemp = os.path.join(tempfile.gettempdir(), "Exoside", "QuadRemesher", "Blender")
os.makedirs(QRTemp, exist_ok=True)
settingsFile = os.path.join(QRTemp, 'RetopoSettings.txt')
inputFbx = os.path.join(QRTemp, 'inputMesh.fbx')
retopoFbx = os.path.join(QRTemp, 'retopo.fbx')
progressFile = os.path.join(QRTemp, 'progress.txt')

print("=" * 60)
print("QR Auto - Blender 5.1")
print("=" * 60)
print(f"Engine: {ENGINE}")
print(f"Engine exists: {os.path.exists(ENGINE)}")

# 1. 打开高模(含眼窝版, 2026-08-21起用01A眼窝输出)
blend_path = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
print(f"\n1. Loading: {blend_path}")
bpy.ops.wm.open_mainfile(filepath=blend_path)

# 2. 选中网格
mesh = [o for o in bpy.data.objects if o.type == "MESH"][0]
bpy.ops.object.select_all(action="DESELECT")
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
print(f"2. Selected: {mesh.name} ({len(mesh.data.polygons):,} faces)")

# 2.5 清理网格: 焊接重复顶点 + 修补边界
# 根因: 未焊接的破碎网格(大量重复顶点/边界边)会让xremesh在~21%处死锁
# 自适应阈值：按模型尺寸缩放
import bmesh
mn_qr = [min(v.co.x for v in mesh.data.vertices), min(v.co.y for v in mesh.data.vertices), min(v.co.z for v in mesh.data.vertices)]
mx_qr = [max(v.co.x for v in mesh.data.vertices), max(v.co.y for v in mesh.data.vertices), max(v.co.z for v in mesh.data.vertices)]
model_h = mx_qr[2] - mn_qr[2]
weld_d = max(0.0001, model_h * 0.00006)
print(f"  Adaptive weld dist: {weld_d:.6f} (height={model_h:.3f})")
bm = bmesh.new()
bm.from_mesh(mesh.data)
before_v = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_d)
after_weld = len(bm.verts)
# 填补小孔洞(开放边界是xremesh卡死的主因, 加上限防异常)
filled = 0
attempts = 0
for e in list(bm.edges):
    if len(e.link_faces) == 1:
        attempts += 1
        if attempts > 30000:
            break
        try:
            res = bmesh.ops.edgeloop_fill(bm, edges=[e])
            filled += len(res.get("faces", []))
        except Exception:
            pass
bm.to_mesh(mesh.data)
bm.free()
mesh.data.update()
print(f"2.5 Cleanup: {before_v:,} -> {after_weld:,} verts (welded {before_v-after_weld:,}), filled {filled} hole faces")

# 3. 导出FBX
print(f"\n3. Exporting FBX...")
bpy.ops.export_scene.fbx(filepath=inputFbx, use_selection=True)
fbx_mb = os.path.getsize(inputFbx) / 1024 / 1024
print(f"   FBX: {fbx_mb:.1f} MB")

# 4. 写settings
print(f"\n4. Writing settings...")
with open(settingsFile, "w") as f:
    f.write('HostApp=Blender\n')
    f.write(f'FileIn="{inputFbx}"\n')
    f.write(f'FileOut="{retopoFbx}"\n')
    f.write(f'ProgressFile="{progressFile}"\n')
    f.write('TargetQuadCount=140000\n')  # 14万quad ≈ 28万三角面（比例调整后模型更大）
    f.write('CurvatureAdaptivness=80\n')
    f.write('ExactQuadCount=0\n')
    f.write('UseVertexColorMap=0\n')
    f.write('UseMaterialIds=0\n')
    f.write('UseIndexedNormals=0\n')
    f.write('AutoDetectHardEdges=1\n')
    # 不写SymAxis：模型纹理不对称，强制对称拓扑会导致纹理错位
print("   Settings written")

# 清理旧输出
for p in [retopoFbx, progressFile]:
    if os.path.exists(p):
        os.remove(p)

# 5. 启动引擎
print(f"\n5. Starting xremesh...")
engine_dir = os.path.dirname(ENGINE)
proc = subprocess.Popen(
    [ENGINE, "-s", settingsFile],
    cwd=engine_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
print(f"   PID: {proc.pid}")

# 6. 轮询进度
print(f"\n6. Waiting...")
start = time.time()
last_pct = -1
while proc.poll() is None:
    time.sleep(2)
    elapsed = time.time() - start
    if os.path.exists(progressFile):
        try:
            with open(progressFile, "r") as pf:
                lines = pf.read().splitlines()
            if lines:
                val = float(lines[0])
                if 0 < val < 1:
                    pct = int(99.0 * val + 1.0)
                    if pct != last_pct:
                        print(f"   Progress: {pct}% ({elapsed:.0f}s)")
                        last_pct = pct
                elif val == 2:
                    print(f"   Progress: 100% ({elapsed:.0f}s)")
                elif val < 0:
                    msg = lines[1] if len(lines) > 1 else "unknown"
                    print(f"   ERROR: {msg} (code={val})")
        except:
            pass

rc = proc.returncode
elapsed = time.time() - start
print(f"\n   Return code: {rc} ({elapsed:.0f}s)")

# 7. 检查结果
if not os.path.exists(retopoFbx):
    print("ERROR: retopo.fbx not generated!")
    sys.exit(1)

size_mb = os.path.getsize(retopoFbx) / 1024 / 1024
print(f"7. Result: {size_mb:.1f} MB")

# 8. 导入结果
print(f"\n8. Importing...")
bpy.ops.import_scene.fbx(filepath=retopoFbx)
qr_obj = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
qr_obj.name = mesh.name + "_QR"
faces = len(qr_obj.data.polygons)
print(f"   QR mesh: {qr_obj.name}, {faces:,} faces")

# 9. 清理原始高模
for obj in list(bpy.data.objects):
    if obj != qr_obj and obj.type == "MESH":
        bpy.data.objects.remove(obj, do_unlink=True)
print("9. Cleaned original mesh")

# 10. 保存
output_blend = os.path.join(OUT_02, "02_qr_150k.blend")
output_fbx = os.path.join(OUT_02, "02_qr_150k.fbx")
bpy.ops.wm.save_as_mainfile(filepath=output_blend)
print(f"10. Saved: {output_blend}")

bpy.ops.object.select_all(action="DESELECT")
qr_obj.select_set(True)
bpy.context.view_layer.objects.active = qr_obj
bpy.ops.export_scene.fbx(filepath=output_fbx, use_selection=True,
    mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
print(f"    Exported: {output_fbx}")

# 验证
import bmesh
bm = bmesh.new()
bm.from_mesh(qr_obj.data)
quads = sum(1 for f in bm.faces if len(f.verts) == 4)
tris = sum(1 for f in bm.faces if len(f.verts) == 3)
nm = sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
print(f"\n=== Verification ===")
print(f"Faces: {faces:,}")
print(f"Quads: {quads:,} ({quads/faces*100:.1f}%)")
print(f"Tris: {tris}")
print(f"Non-manifold: {nm}")
print(f"As triangles: {quads*2+tris:,}")
if quads*2+tris > 300000:
    print(f"⚠ 三角面超限: {quads*2+tris:,} > 300,000")
else:
    print(f"✓ 三角面达标: {quads*2+tris:,} ≤ 300,000")
print("\nDONE")
