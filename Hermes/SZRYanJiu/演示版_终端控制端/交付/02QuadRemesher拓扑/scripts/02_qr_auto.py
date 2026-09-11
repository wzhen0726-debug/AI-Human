import bpy, os, sys, subprocess, tempfile, time, math

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\交付"
# 2026-09-09 用户明确: 测试阶段产物权威位置是 02QR拓扑/输出/(GUI核验处), 不是交付/.
# 交付/ 是流程定稿后才整理的位置; 测试期所有QR产物直接写到 02QR拓扑/输出/.
OUT_02 = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\02QR拓扑\输出"
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

# 1. 打开高模(01a眼窝+材质分区版; 2026-09-08 用户方案: 眼窝独立材质, QR只勾"使用材质"引导)
blend_path = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket_qr.blend")
print(f"\n1. Loading: {blend_path}")
bpy.ops.wm.open_mainfile(filepath=blend_path)

# 1.5 另存QR前高模分区检查副本到输出目录(2026-09-09 用户要求: 输出目录需含高模眼窝分区检查文件)
#     这是QR的输入高模(带EyeSocket分区), 供用户核验"送进QR的分区对不对".
hi_check = os.path.join(OUT_02, "02QR输入_眼窝材质分区_高模.blend")
bpy.ops.wm.save_as_mainfile(filepath=hi_check)
print(f"1.5 高模分区检查副本: {hi_check}")
# 另存后重新打开原始高模, 保证后续在正确上下文操作(save_as会切换当前文件路径)
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

# 2.6 材质分区校验(2026-09-08 用户方案): QR只勾"使用材质", 沿眼窝/皮肤材质边界布线.
# 材质边界=碗面与皮肤的公共边=眼睑缘rim → QR沿rim布线, 保住眼窝结构.
# 实测四配置对比(眼窝区双向Chamfer + rim折角 + 拓扑质量):
#   A_hard(角度检测硬边,旧默认):  141,951面 quad100.0% 非流形10  rim折角max35.7° chamfer中位1.690mm max8.030mm
#   B_n45_edge(法向分割45°):     151,684面 quad 99.3% 非流形58  rim折角max79.3° chamfer中位1.296mm max3.330mm
#   D_mat_only(只用材质,本方案):  144,611面 quad 99.9% 非流形 0  rim折角max80.7° chamfer中位1.242mm max7.339mm
#   E_mat_n45(材质+法向):        144,088面 quad 98.7% 非流形2962 rim折角max178.0° chamfer中位1.412mm
# 选D: 非流形0(下游UV/烘焙/绑定不再受拖累)、quad99.9%、chamfer中位最优、棱线锐度=旧默认2.3倍.
#   D的chamfer max 7.3mm全部落在rim过渡带(碗底深处0个离群,碗底保留0.81/1.85mm), 由烘焙法线贴图补偿.
# 前提: 01a的 assign_socket_material.py 已给眼窝碗面赋独立材质 EyeSocket(输出_qr.blend, 不动烘焙源文件).
mats = [m.name if m else None for m in mesh.data.materials]
import collections as _c
_mi = [0] * len(mesh.data.polygons)
mesh.data.polygons.foreach_get("material_index", _mi)
_cnt = dict(_c.Counter(_mi))
if len(_cnt) < 2:
    raise AssertionError(f"高模只有{len(_cnt)}种材质{_cnt} — 缺眼窝独立材质, QR无材质边界可引导! "
                         f"先跑 01A眼窝与眼球/scripts/assign_socket_material.py")
print(f"2.6 材质分区校验: 槽={mats} 面分布={_cnt} → 材质边界可引导QR沿rim布线")

# 2.7 缓存高模rim环内外拓扑真值(2026-09-10 v53, 用户方案):
#   掏rim环时碗面已打tag/赋EyeSocket材质 → rim环内=碗面, 环状连通循环(掏洞拓扑保证).
#   QR重铺后拓扑边界丢失, 8.5b用此缓存把每个QR面传递回高模最近面的内外归属.
#   必须在此缓存: 8.5会删除高模对象.
import numpy as _np
from mathutils.bvhtree import BVHTree as _BVHTree
_mw_hi = _np.array(mesh.matrix_world)
_co_hi = _np.empty(len(mesh.data.vertices)*3); mesh.data.vertices.foreach_get("co",_co_hi)
_HV_hi = _co_hi.reshape(-1,3)@_mw_hi[:3,:3].T+_mw_hi[:3,3]
# ⚠必须用FromPolygons(数据拷贝), 不能用FromObject(引用对象):
#   8.5步会删除高模对象, FromObject的BVH底层数据悬空 → find_nearest大面积返回None
#   (v53首跑教训: 138834/144536面'超阈值', 实为悬空引用查询失败).
_verts_hi=[tuple(v) for v in _co_hi.reshape(-1,3)]
_polys_hi=[list(p.vertices) for p in mesh.data.polygons]
_HI_SVC = _BVHTree.FromPolygons(_verts_hi, _polys_hi)
del _verts_hi, _polys_hi   # BVH已持有拷贝, 释放大列表
_HI_mi = _np.zeros(len(mesh.data.polygons),dtype=_np.int32); mesh.data.polygons.foreach_get("material_index",_HI_mi)
# rim环内判定: EyeSocket材质槽(权威, assign按tag==2赋)
_si_hi=[i for i,m in enumerate(mesh.data.materials) if m and "EyeSocket" in m.name]
assert _si_hi, "高模无EyeSocket材质槽 — assign_socket_material未跑?"
_HI_BOWL=(_HI_mi==_si_hi[0])
# 碗面中心(世界坐标)缓存 — 8.5b force-cover用: 每个碗面必须被红QR面覆盖(v54实测center判据缺红105→force缺红0)
_HI_HC=_np.array([_HV_hi[list(mesh.data.polygons[i].vertices)].mean(axis=0) for i in _np.where(_HI_BOWL)[0]])
# 高模bbox对角线(供8.5b查询阈值自适应)
_lo=_HV_hi.min(axis=0); _up=_HV_hi.max(axis=0); _HI_BBOX_DIAG=float(_np.linalg.norm(_up-_lo))
print(f"2.7 高模rim环内外真值缓存: 碗面(rim环内)={int(_HI_BOWL.sum())}面/{len(_HI_BOWL)} BVH就绪 bbox对角线={_HI_BBOX_DIAG*1000:.0f}mm")

# 3. 导出FBX (材质分区靠material_index随FBX的smoothing/material槽带走; 不需要法向分割)
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
    # 2026-09-08 用户方案(实测D组最优): 只用材质引导, 取消法向分割与角度检测硬边
    f.write('UseMaterialIds=1\n')       # ✓使用材质: 沿眼窝/皮肤材质边界(=rim)布线
    f.write('UseIndexedNormals=0\n')    # ✗取消法向分割
    f.write('AutoDetectHardEdges=0\n')  # ✗取消角度检测硬边(实测抹平眼窝折角35.7°)
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

# 8.5 清理原始高模(先清: 检查副本只含QR低模, 不混190万面高模, 文件小且干净)
for obj in list(bpy.data.objects):
    if obj != qr_obj and obj.type == "MESH":
        bpy.data.objects.remove(obj, do_unlink=True)
print("8.5 Cleaned original mesh")

# 8.5b 高模材质传递(2026-09-10 v53, 用户方案): 不做任何几何猜测.
#   历史: v1(09-09)用XZ-pip+depth几何判据 — pip有3D盲区(碗口面XZ翻出rim轮廓被漏判, 实测13面),
#   v52(09-10)去掉pip改纯depth — 仍有平面近似盲区, 用户仍见侵入. 几何猜测路线判死.
#   v53(用户方案): 掏rim环时碗面已赋EyeSocket材质(rim环内=环状连通循环, 掏洞拓扑保证).
#   QR重铺后每个面找高模最近面(BVH, 2.7段缓存), 直接继承其rim环内/外归属 — 零猜测.
#   效果: QR红区=高模碗面的最近面投影, 材质分界严格=rim环, 环内全部红色循环, 无侵入无溢出.
_qme=qr_obj.data; _qmw=_np.array(qr_obj.matrix_world)
_qco=_np.empty(len(_qme.vertices)*3); _qme.vertices.foreach_get("co",_qco)
_QV=_qco.reshape(-1,3)@_qmw[:3,:3].T+_qmw[:3,3]
_qC=_np.array([_QV[list(_qme.polygons[i].vertices)].mean(axis=0) for i in range(len(_qme.polygons))])
_qsi=[i for i,m in enumerate(_qme.materials) if m and "EyeSocket" in m.name]
if _qsi:
    _qsi=_qsi[0]
    # 每个QR面中心 → 高模最近面(BVHTree.find_nearest返回location,normal,index,distance; 无find方法)
    # ⚠坐标系: BVHTree.FromObject建在高模局部空间, 查询点必须从世界坐标变换到高模局部
    #   (v53首跑教训: 世界坐标直接查询 → 141154/144811面返回None, 只有眼窝附近巧合命中)
    _inv_hi=_np.linalg.inv(_mw_hi)
    _qC_local=_qC@_inv_hi[:3,:3].T+_inv_hi[:3,3]
    _hit=[_HI_SVC.find_nearest(_q) for _q in _qC_local]
    _idx=_np.array([h[2] if h[0] is not None else -1 for h in _hit])
    _dist=_np.array([abs(h[3]) if h[0] is not None else 1e9 for h in _hit])
    _d_mm=_dist*1000
    # 距离过远的查询不可信(应在QR贴合面上, 距离≈0): 用bbox尺度自适应阈值, 超限的保留QR原材质
    # ⚠单位: _HI_BBOX_DIAG是米, _d_mm是毫米 — v53二跑教训: 米阈值比毫米距离, 5567/144254误判可信
    _tol_mm=float(_HI_BBOX_DIAG)*1000*0.002   # 0.2%模型对角线≈5.1mm
    _trust=_d_mm<=_tol_mm
    _bowl_hit=_HI_BOWL[_idx]
    _qmi=_np.zeros(len(_qme.polygons),dtype=_np.int32); _qme.polygons.foreach_get("material_index",_qmi)
    _qmi_new=_qmi.copy()
    _qmi_new[_trust&_bowl_hit]=_qsi    # 最近高模面在rim环内 → 红
    _qmi_new[_trust&~_bowl_hit]=0      # 最近高模面在rim环外 → 灰
    _fix_to_red=int(((_trust&_bowl_hit)&(_qmi!=_qsi)).sum())
    _fix_to_skin=int(((_trust&~_bowl_hit)&(_qmi==_qsi)).sum())
    _qme.polygons.foreach_set("material_index",_qmi_new); _qme.update()
    print(f"8.5b 高模材质传递(v53): 补红={_fix_to_red} 收灰={_fix_to_skin} 查询可信={int(_trust.sum())}/{len(_qC)} 距离max={_d_mm.max():.2f}mm")
    if int((_trust).sum())<len(_qC):
        print(f"  ⚠ {int((~_trust).sum())}面查询超阈值{_tol_mm:.1f}mm保留原材质(应为0)")
    # 8.5c force-cover(v54): 每个高模碗面必须被红QR面覆盖.
    #   根因: rim边界QR面横跨碗/皮肤, 面中心恰落皮肤侧 → center判据判灰 → 实测缺红105
    #   (R下睑一条灰带横切红区, 用户见'侵入'). 修: 碗面中心→QR最近面强制红.
    #   实测(v54 diag): 缺红105→0, 新增红34面全部距高模<0.94mm(贴rim跨界歧义面, 非真溢出).
    #   方向选择: 薄红边(rim离散化必然)远好于灰条带(用户不可接受).
    _SVC_Q=_BVHTree.FromPolygons([tuple(v) for v in _QV],[list(p.vertices) for p in _qme.polygons])
    _force=set()
    for _p in _HI_HC:
        _h=_SVC_Q.find_nearest(_p)
        if _h[0] is not None: _force.add(_h[2])
    _force_arr=_np.fromiter(_force,dtype=_np.int64,count=len(_force))
    _added=int((_qmi_new[_force_arr]!=_qsi).sum())
    _qmi_new[_force_arr]=_qsi
    _qme.polygons.foreach_set("material_index",_qmi_new); _qme.update()
    del _SVC_Q
    print(f"8.5c force-cover(v54): 碗面{len(_HI_HC)}个 → QR覆盖红面{len(_force)}个, 新增强制红={_added} (缺红应为0)")
    # 8.5d 灰楔消除(v55, 用户报"还是有侵入"): force-cover只覆盖碗面中心最近QR面,
    #   漏掉rim处骑跨面 — 一个QR面横跨rim曲线, 中心在皮肤侧但部分顶点/边踩碗 → 视觉灰楔刺入红区.
    #   方案A(零拓扑改动): rim域灰面(红面邻接+扩1圈)多点采样(顶点+边中点+中心),
    #   任一采样点踩碗 → 赋红. 不改网格(对比方案B弦切分会产生223非流形边, 弃用).
    #   实测: rim域灰面186, 任一踩碗33 → 赋红后残留灰楔0, 非流形边不变(4), quad99.98%.
    #   方向: 宁可rim边缘薄红溢出(用户可接受), 不要灰楔侵入(用户明确不可接受).
    def _on_bowl_w(_Pw):
        # ⚠v55教训(face50571): 采样点恰在rim曲线上(距高模0.00mm)时, 最近面在碗面/皮肤间二义,
        #   生产BVH(清理后网格)判皮肤、验证BVH(原始网格)判碗面 → 同面两判. 修: 范围查询,
        #   0.3mm邻域内存在任一高模碗面即算踩碗. rim曲线点天然碗皮共享→赋红(宁红勿灰);
        #   真皮肤面距碗面>数mm不受影响.
        _Pl=_Pw@_inv_hi[:3,:3].T+_inv_hi[:3,3]
        _hits=_HI_SVC.find_nearest_range(_Pl, 0.0003)
        return any(_HI_BOWL[_h[2]] for _h in _hits)
    # bbox圈定眼区扫全部灰面(v55教训: 只扫"红面1圈邻居"漏了face494/507 — 它们被不踩碗的灰面隔开,
    #   不与红面直接相邻). 改用碗面中心bbox+15mm圈定眼区, 对区内所有灰面采样, 踩碗即红. 不依赖红邻接.
    _bb_lo=_HI_HC.min(axis=0)-0.015; _bb_hi=_HI_HC.max(axis=0)+0.015
    _in_bb=(_qC[:,0]>=_bb_lo[0])&(_qC[:,0]<=_bb_hi[0])&(_qC[:,1]>=_bb_lo[1])&(_qC[:,1]<=_bb_hi[1])&(_qC[:,2]>=_bb_lo[2])&(_qC[:,2]<=_bb_hi[2])
    _gray_zone=_np.where(_in_bb & (_qmi_new!=_qsi))[0]
    _wedge=[]
    for _fi in _gray_zone:
        _vs=list(_qme.polygons[_fi].vertices)
        _P=_QV[_vs]
        _samp=[_P.mean(axis=0)]+[tuple(p) for p in _P]
        for _i in range(len(_P)): _samp.append(tuple((_P[_i]+_P[(_i+1)%len(_P)])/2))
        if any(_on_bowl_w(_np.array(s)) for s in _samp): _wedge.append(int(_fi))
    _wedge_arr=_np.fromiter(_wedge,dtype=_np.int64,count=len(_wedge))
    if len(_wedge_arr): _qmi_new[_wedge_arr]=_qsi
    _qme.polygons.foreach_set("material_index",_qmi_new); _qme.update()
    print(f"8.5d 灰楔消除(v55): 眼区bbox内灰面{len(_gray_zone)} 踩碗赋红={len(_wedge)} (残留灰楔应=0)")
else:
    print("8.5b ⚠ QR输出无EyeSocket槽, 跳过材质传递")

# 8.6 材质分区检查副本(2026-09-08 用户要求): 保存QR引擎的真实输出(保留眼窝EyeSocket材质分区),
#     供用户核验"QR是否真的沿眼窝材质边界(=rim)布线". 必须在材质合并(8.7)之前存.
#     这是QR的真实产物, 不是按rim重新赋材质(那等于自证, 看不出QR行为).
import collections as _cc
_nmat_raw = len(qr_obj.data.materials)
check_blend = os.path.join(OUT_02, "02_qr_150k_材质分区检查.blend")
if _nmat_raw > 1:
    bpy.ops.wm.save_as_mainfile(filepath=check_blend)
    _mi_chk = [0] * len(qr_obj.data.polygons)
    qr_obj.data.polygons.foreach_get("material_index", _mi_chk)
    _cnt_chk = dict(_cc.Counter(_mi_chk))
    _mnames = [m.name if m else None for m in qr_obj.data.materials]
    print(f"   材质分区检查副本: {os.path.basename(check_blend)} 槽={_mnames} 面分布={_cnt_chk}")
else:
    print(f"   ⚠ QR未保留材质分区({_nmat_raw}槽), 无法生成检查副本 — UseMaterialIds可能未生效!")

# 8.7 材质合并(2026-09-08 修红眼窝bug): QR的UseMaterialIds会保留眼窝EyeSocket引导材质
#     (饱和红0.8/0.15/0.15). 材质引导只为让QR沿rim布线, 布线完成后必须丢弃 —
#     否则红材质槽随低模流到03/04, 04烘焙只替换材质槽0, 眼窝面(material_index=1)仍挂红槽
#     → 渲染/烘焙产物眼窝发红(实测真bug: 02/03/04都残留EyeSocket.001红槽).
#     源头合并最干净: 所有面归槽0, 删多余槽. QR输出本就是单材质灰模, 肤色在04烘焙才贴.
_nmat = len(qr_obj.data.materials)
if _nmat > 1:
    qr_obj.data.polygons.foreach_set("material_index", [0] * len(qr_obj.data.polygons))
    while len(qr_obj.data.materials) > 1:
        # Blender 5.1: materials.pop() 只接受 index, 不再有 update_data 参数
        qr_obj.data.materials.pop(index=len(qr_obj.data.materials) - 1)
    qr_obj.data.update()
    _chk = [m.name if m else None for m in qr_obj.data.materials]
    print(f"   材质合并: {_nmat}槽 -> {len(_chk)}槽 {_chk} (丢弃EyeSocket引导材质)")
    assert len(_chk) == 1, f"材质合并失败! 仍有多槽={_chk}"
else:
    print(f"   材质槽={_nmat}(QR未保留分区, 无需合并)")

# 9. 保存主产物(单材质, 供下游03/04)
output_blend = os.path.join(OUT_02, "02_qr_150k.blend")
output_fbx = os.path.join(OUT_02, "02_qr_150k.fbx")
bpy.ops.wm.save_as_mainfile(filepath=output_blend)
print(f"9. Saved: {output_blend}")

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
