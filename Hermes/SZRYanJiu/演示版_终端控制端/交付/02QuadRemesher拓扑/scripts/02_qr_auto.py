import bpy, os, sys, subprocess, tempfile, time, math

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
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

# 1. 打开高模(01a眼窝版; 2026-09-08 A方案: rim预锐化机制已删除, 直接用眼窝高模)
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

# 2.6 法向分割预处理(2026-09-08): 让QR沿高模的真实折角布线, 保住眼窝等结构
# 实测对比(眼窝区双向Chamfer, 4种配置):
#   A 仅角度检测硬边(旧默认): 高模→低模中位1.690mm p95=3.551mm max=8.030mm, rim折角max=35.7°(棱线被抹平)
#   B 法向分割45°+EDGE导出:   高模→低模中位1.296mm p95=2.418mm max=3.330mm, rim折角max=79.3°(棱线保留)
#   → B 细节丢失-23%/最差处-59%/棱线锐度2.2倍/眼窝顶点密度+47%, 代价仅面数+6.9%、quad 100%→99.3%
# 插件tooltip前提: UseIndexedNormals"仅在启用SmoothShade+AutoSmooth时才有用"
#   Blender 5.1 已移除 use_auto_smooth/auto_smooth_angle, 正解=mesh.set_sharp_from_angle()
# SHARP_ANGLE_DEG是二面角阈值(几何内禀量, 与体型无关), 不违反"按身高/bbox比例"的自适应原则
SHARP_ANGLE_DEG = 45.0
for p in mesh.data.polygons:
    p.use_smooth = True
if hasattr(mesh.data, 'set_sharp_from_angle'):
    mesh.data.set_sharp_from_angle(angle=math.radians(SHARP_ANGLE_DEG))
else:
    # 退路: bmesh逐边按二面角标sharp
    bm_s = bmesh.new(); bm_s.from_mesh(mesh.data); bm_s.edges.ensure_lookup_table()
    thr = math.radians(SHARP_ANGLE_DEG)
    for e in bm_s.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle() > thr)
    bm_s.to_mesh(mesh.data); bm_s.free()
mesh.data.update()
bm_c = bmesh.new(); bm_c.from_mesh(mesh.data); bm_c.edges.ensure_lookup_table()
n_sharp = sum(1 for e in bm_c.edges if not e.smooth)
bm_c.free()
print(f"2.6 法向分割预处理: shade_smooth全面 + set_sharp_from_angle({SHARP_ANGLE_DEG}°) "
      f"-> 硬边{n_sharp:,}/{len(mesh.data.edges):,} ({n_sharp/len(mesh.data.edges)*100:.2f}%)")

# 3. 导出FBX (mesh_smooth_type='EDGE'把sharp边写成FBX法向分割, QR才能读到)
print(f"\n3. Exporting FBX...")
bpy.ops.export_scene.fbx(filepath=inputFbx, use_selection=True, mesh_smooth_type='EDGE')
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
    f.write('UseMaterialIds=1\n')   # 启用材质边界→rim锐利 (2026-08-24)
    # 2026-09-08 改用法向分割(见2.6注释的实测对比): 沿高模真实折角布线, 保住眼窝棱线
    f.write('UseIndexedNormals=1\n')    # 使用法向分割(原0=关闭)
    f.write('AutoDetectHardEdges=0\n')  # 关闭角度检测硬边(原1=开启; 实测该模式抹平眼窝折角)
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
# 归零FBX导入残留旋转(轴向转换浮点残差~-1.6e-7rad≈-0.000009°)
bpy.ops.object.select_all(action="DESELECT")
qr_obj.select_set(True)
bpy.context.view_layer.objects.active = qr_obj
_rot_before = tuple(qr_obj.rotation_euler)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
print(f"   旋转归零: {_rot_before} -> {tuple(qr_obj.rotation_euler)}")
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
